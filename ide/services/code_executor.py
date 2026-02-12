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
from typing import Dict, List, Any, Optional

from config import PROJECT_ROOT, ALLOWED_EXAMPLES_DIR

# 导入调试服务
try:
    from ide.services.debug_service import get_debug_service, get_error_analyzer
    _debug_service_available = True
except ImportError:
    _debug_service_available = False

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


def execute_hpl(file_path, debug_mode: bool = False, 
                call_target: Optional[str] = None,
                call_args: Optional[List] = None) -> Dict[str, Any]:
    """
    执行 HPL 文件
    使用 hpl_runtime 执行代码
    在受限环境中运行
    
    Args:
        file_path: HPL文件路径
        debug_mode: 是否启用调试模式
        call_target: 可选的调用目标函数（调试模式）
        call_args: 可选的调用参数（调试模式）
    
    Returns:
        dict: 执行结果，包含success、output、error等字段
    """
    # 如果启用调试模式，使用调试执行
    if debug_mode:
        return execute_with_debug(file_path, call_target, call_args)
    

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
        call_stack = []
        try:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_tb:
                # 提取完整的调用栈
                tb_frames = traceback.extract_tb(exc_tb)
                for frame in tb_frames:
                    call_stack.append({
                        'filename': frame.filename,
                        'line': frame.lineno,
                        'function': frame.name,
                        'code': frame.line
                    })
                # 最后一帧的行号
                last_frame = tb_frames[-1]
                line_no = last_frame.lineno
        except Exception:
            pass
        
        # 尝试获取更详细的错误信息（如果是 HPL 运行时错误）
        error_details = {
            'success': False,
            'error': error_msg,
            'line': line_no,
            'traceback': tb,
            'call_stack': call_stack if call_stack else None
        }
        
        # 如果有调用栈，添加格式化后的调用栈信息
        if call_stack:
            formatted_stack = []
            for i, frame in enumerate(call_stack):
                formatted_stack.append(f"  {i}: {frame['function']} at {frame['filename']}:{frame['line']}")
            error_details['formatted_call_stack'] = '\n'.join(formatted_stack)
        
        return error_details


def execute_with_debug(file_path: str, 
                       call_target: Optional[str] = None,
                       call_args: Optional[List] = None) -> Dict[str, Any]:
    """
    使用调试模式执行 HPL 文件
    提供详细的执行跟踪、变量监控和性能分析
    
    Args:
        file_path: HPL文件路径
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
    
    Returns:
        dict: 包含执行结果和调试信息
    """
    if not _debug_service_available:
        logger.warning("调试服务不可用，回退到标准执行模式")
        return execute_hpl(file_path, debug_mode=False)
    
    try:
        # 使用调试服务执行
        debug_service = get_debug_service()
        result = debug_service.debug_file(file_path, call_target, call_args)
        
        # 格式化调试结果
        formatted_result = {
            'success': result.get('success', False),
            'error': result.get('error'),
            'line': result.get('line'),
            'column': result.get('column'),
            'output': _extract_output_from_trace(result),
            'debug_info': result.get('debug_info', {})
        }
        
        # 添加变量监控信息
        if 'variable_snapshots' in formatted_result['debug_info']:
            snapshots = formatted_result['debug_info']['variable_snapshots']
            if snapshots:
                formatted_result['final_variables'] = snapshots[-1]
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"调试执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': f"调试执行失败: {str(e)}",
            'debug_info': {}
        }


def _extract_output_from_trace(result: Dict[str, Any]) -> str:
    """
    从执行跟踪中提取输出信息
    
    Args:
        result: 调试结果
    
    Returns:
        str: 提取的输出内容
    """
    output_lines = []
    
    # 从执行跟踪中提取 echo 语句的输出
    trace = result.get('debug_info', {}).get('execution_trace', [])
    for entry in trace:
        if entry.get('type') == 'FUNCTION_CALL':
            details = entry.get('details', {})
            if details.get('name') == 'echo':
                args = details.get('args', [])
                output_lines.append(' '.join(str(arg) for arg in args))
    
    return '\n'.join(output_lines) if output_lines else ''


def get_execution_trace(file_path: str) -> List[Dict[str, Any]]:
    """
    获取 HPL 文件的执行跟踪（不实际执行，仅预览）
    
    Args:
        file_path: HPL文件路径
    
    Returns:
        list: 执行跟踪条目列表
    """
    if not _debug_service_available:
        logger.warning("调试服务不可用")
        return []
    
    try:
        debug_service = get_debug_service()
        result = debug_service.debug_file(file_path)
        return result.get('debug_info', {}).get('execution_trace', [])
    except Exception as e:
        logger.error(f"获取执行跟踪失败: {e}")
        return []


def get_variable_snapshots(file_path: str) -> List[Dict[str, Any]]:
    """
    获取 HPL 文件执行过程中的变量快照
    
    Args:
        file_path: HPL文件路径
    
    Returns:
        list: 变量快照列表
    """
    if not _debug_service_available:
        logger.warning("调试服务不可用")
        return []
    
    try:
        debug_service = get_debug_service()
        result = debug_service.debug_file(file_path)
        return result.get('debug_info', {}).get('variable_snapshots', [])
    except Exception as e:
        logger.error(f"获取变量快照失败: {e}")
        return []


def analyze_execution_error(file_path: str, error: Exception, 
                           source_code: str) -> Dict[str, Any]:
    """
    分析执行错误并提供上下文和建议
    
    Args:
        file_path: HPL文件路径
        error: 异常对象
        source_code: 源代码
    
    Returns:
        dict: 错误分析结果
    """
    if not _debug_service_available:
        return {
            'error_type': type(error).__name__,
            'message': str(error),
            'suggestions': ['检查代码逻辑', '参考 HPL 语法手册']
        }
    
    try:
        analyzer = get_error_analyzer()
        return analyzer.analyze_error(error, source_code)
    except Exception as e:
        logger.error(f"分析错误失败: {e}")
        return {
            'error_type': type(error).__name__,
            'message': str(error),
            'suggestions': ['检查代码逻辑']
        }
