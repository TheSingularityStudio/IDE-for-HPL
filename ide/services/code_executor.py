"""
HPL代码执行服务
处理HPL代码的实际执行
"""

import sys
import os
import io
import contextlib
import traceback
import logging

from config import PROJECT_ROOT, ALLOWED_EXAMPLES_DIR

logger = logging.getLogger(__name__)

# 运行时可用性检查（延迟加载）
_hpl_runtime_available = None


def check_runtime_available():
    """
    检查hpl_runtime是否可用
    
    Returns:
        bool: 是否可用
    """
    global _hpl_runtime_available
    
    if _hpl_runtime_available is None:
        try:
            import hpl_runtime
            _hpl_runtime_available = True
            logger.info("hpl-runtime 已加载")
        except ImportError:
            _hpl_runtime_available = False
            logger.warning("hpl-runtime 未安装。代码执行功能将不可用。")
    
    return _hpl_runtime_available


def execute_hpl(file_path):
    """
    执行 HPL 文件
    使用 hpl_runtime 执行代码
    在受限环境中运行
    
    Args:
        file_path: HPL文件路径
    
    Returns:
        dict: 执行结果，包含success、output、error等字段
    """
    # 添加 examples 目录到 Python 模块搜索路径
    if ALLOWED_EXAMPLES_DIR not in sys.path:
        sys.path.insert(0, ALLOWED_EXAMPLES_DIR)
    
    try:
        # 修复：从hpl_runtime直接导入，而不是从子模块
        from hpl_runtime import HPLParser, HPLEvaluator, ImportStatement
        
        # 捕获输出
        output_buffer = io.StringIO()
        
        with contextlib.redirect_stdout(output_buffer):
            parser = HPLParser(file_path)
            classes, objects, functions, main_func, call_target, call_args, imports = parser.parse()
            
            evaluator = HPLEvaluator(classes, objects, functions, main_func, call_target, call_args)

            
            # 处理顶层导入
            for imp in imports:
                module_name = imp['module']
                alias = imp.get('alias', module_name)
                import_stmt = ImportStatement(module_name, alias)
                evaluator.execute_import(import_stmt, evaluator.global_scope)
            
            evaluator.run()
        
        output = output_buffer.getvalue()
        
        return {
            'success': True,
            'output': output
        }
        
    except ImportError as e:
        error_msg = f"hpl-runtime 导入错误: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
        }

    except SyntaxError as e:
        error_msg = f"HPL 语法错误 (行 {e.lineno}, 列 {e.offset or 1}): {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'line': e.lineno,
            'column': e.offset or 1,
            'type': 'syntax_error',
            'text': e.text
        }

    except Exception as e:
        error_msg = str(e)
        
        # 尝试提取行号信息
        tb = traceback.format_exc()
        logger.error(f"执行错误: {error_msg}\n{tb}")
        
        # 尝试从 traceback 中提取行号
        line_no = None
        try:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_tb:
                last_frame = traceback.extract_tb(exc_tb)[-1]
                line_no = last_frame.lineno
        except Exception:
            pass
        
        return {
            'success': False,
            'error': error_msg,
            'line': line_no,
            'traceback': tb
        }
