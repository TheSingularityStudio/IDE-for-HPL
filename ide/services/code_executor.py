"""
HPL代码执行服务
处理HPL代码的实际执行
基于 HPLEngine 实现统一的执行接口
"""

import os
import sys
import io
import contextlib
import logging
from typing import Dict, List, Any, Optional

# 导入核心引擎
try:
    from ide.services.hpl_engine import HPLEngine, execute_code as engine_execute_code, debug_code as engine_debug_code
    from ide.services.hpl_engine import check_runtime_available
    _engine_available = True
except ImportError:
    _engine_available = False

# 导入调试服务
try:
    from ide.services.debug_service import get_debug_service, get_error_analyzer
    _debug_service_available = True
except ImportError:
    _debug_service_available = False

logger = logging.getLogger(__name__)


def check_runtime_available():
    """
    检查hpl_runtime是否可用
    
    Returns:
        bool: 是否可用
    """
    if not _engine_available:
        return False
    
    try:
        import hpl_runtime
        return True
    except ImportError:
        return False


def execute_hpl(file_path, debug_mode: bool = False,
                call_target: Optional[str] = None,
                call_args: Optional[List] = None) -> Dict[str, Any]:
    """
    执行 HPL 文件
    使用 HPLEngine 执行代码
    
    Args:
        file_path: HPL文件路径
        debug_mode: 是否启用调试模式
        call_target: 可选的调用目标函数（调试模式）
        call_args: 可选的调用参数（调试模式）
    
    Returns:
        dict: 执行结果，包含success、output、error等字段
    """
    if not _engine_available:
        return {
            'success': False,
            'error': 'hpl_runtime 不可用，无法执行代码',
            'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
        }
    
    if not os.path.exists(file_path):
        return {
            'success': False,
            'error': f'文件不存在: {file_path}'
        }
    
    try:
        # 使用 HPLEngine 执行
        engine = HPLEngine()
        
        if not engine.load_file(file_path):
            return {
                'success': False,
                'error': f'无法加载文件: {file_path}'
            }
        
        if debug_mode:
            # 调试模式
            result = engine.debug(call_target=call_target, call_args=call_args)
        else:
            # 标准执行模式
            result = engine.execute(call_target=call_target, call_args=call_args)
        
        return result
        
    except ImportError as e:
        error_msg = f"hpl-runtime 导入错误: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
        }
        
    except Exception as e:
        error_msg = f"执行错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'error': error_msg
        }


def execute_hpl_code(code: str, debug_mode: bool = False,
                    call_target: Optional[str] = None,
                    call_args: Optional[List] = None,
                    file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    执行 HPL 代码字符串
    
    Args:
        code: HPL代码字符串
        debug_mode: 是否启用调试模式
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        file_path: 可选的文件路径（用于错误显示）
    
    Returns:
        dict: 执行结果
    """
    if not _engine_available:
        return {
            'success': False,
            'error': 'hpl_runtime 不可用，无法执行代码',
            'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
        }
    
    try:
        # 使用 HPLEngine 执行
        engine = HPLEngine()
        engine.load_code(code, file_path)
        
        if debug_mode:
            # 调试模式
            result = engine.debug(call_target=call_target, call_args=call_args)
        else:
            # 标准执行模式
            result = engine.execute(call_target=call_target, call_args=call_args)
        
        return result
        
    except Exception as e:
        error_msg = f"执行错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'error': error_msg
        }


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
    return execute_hpl(file_path, debug_mode=True, 
                      call_target=call_target, call_args=call_args)


def get_execution_trace(file_path: str) -> List[Dict[str, Any]]:
    """
    获取 HPL 文件的执行跟踪
    
    Args:
        file_path: HPL文件路径
    
    Returns:
        list: 执行跟踪条目列表
    """
    result = execute_hpl(file_path, debug_mode=True)
    return result.get('debug_info', {}).get('execution_trace', [])


def get_variable_snapshots(file_path: str) -> List[Dict[str, Any]]:
    """
    获取 HPL 文件执行过程中的变量快照
    
    Args:
        file_path: HPL文件路径
    
    Returns:
        list: 变量快照列表
    """
    result = execute_hpl(file_path, debug_mode=True)
    return result.get('debug_info', {}).get('variable_snapshots', [])


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


# 便捷函数别名
run_hpl = execute_hpl
run_hpl_code = execute_hpl_code
