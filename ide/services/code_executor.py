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
from ide.services.hpl_engine import HPLEngine, execute_code as engine_execute_code, debug_code as engine_debug_code

# 导入统一的运行时管理器（P0修复：统一运行时检查）
from ide.services.runtime_manager import check_runtime_available, get_runtime_manager


# 导入调试服务
try:
    from ide.services.debug_service import get_debug_service, get_error_analyzer
    _debug_service_available = True
except ImportError:
    _debug_service_available = False

logger = logging.getLogger(__name__)


# 注意：check_runtime_available 现在从 runtime_manager 统一导入
# 本地实现已删除，确保所有模块使用一致的检查逻辑



def execute_hpl(file_path, debug_mode: bool = False,
                call_target: Optional[str] = None,
                call_args: Optional[List] = None,
                input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    执行 HPL 文件
    使用 HPLEngine 执行代码
    
    Args:
        file_path: HPL文件路径
        debug_mode: 是否启用调试模式
        call_target: 可选的调用目标函数（调试模式）
        call_args: 可选的调用参数（调试模式）
        input_data: 可选的输入数据（用于input()函数）
    
    Returns:
        dict: 执行结果，包含success、output、error等字段
    """
    # P0修复：使用统一的运行时检查
    if not check_runtime_available():
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
            result = engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
        else:
            # 标准执行模式
            result = engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)
        
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
        # P1修复：保留详细的错误信息
        error_result = _extract_error_details(e)
        error_msg = f"执行错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 合并详细错误信息
        error_result.update({
            'success': False,
            'error': error_msg
        })
        return error_result


def execute_hpl_code(code: str, debug_mode: bool = False,
                    call_target: Optional[str] = None,
                    call_args: Optional[List] = None,
                    file_path: Optional[str] = None,
                    input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    执行 HPL 代码字符串
    
    Args:
        code: HPL代码字符串
        debug_mode: 是否启用调试模式
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        file_path: 可选的文件路径（用于错误显示）
        input_data: 可选的输入数据（用于input()函数）
    
    Returns:
        dict: 执行结果
    """
    # P0修复：使用统一的运行时检查
    if not check_runtime_available():
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
            result = engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
        else:
            # 标准执行模式
            result = engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)
        
        return result
        
    except Exception as e:
        # P1修复：保留详细的错误信息
        error_result = _extract_error_details(e)
        error_msg = f"执行错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 合并详细错误信息
        error_result.update({
            'success': False,
            'error': error_msg
        })
        return error_result


def _extract_error_details(e: Exception) -> Dict[str, Any]:
    """
    P1修复：从异常中提取详细的错误信息
    
    Args:
        e: 异常对象
        
    Returns:
        dict: 包含详细错误信息的字典
    """
    details = {
        'error_type': type(e).__name__,
    }
    
    # 提取行号信息
    if hasattr(e, 'line'):
        details['line'] = e.line
    elif hasattr(e, 'lineno'):
        details['line'] = e.lineno
    
    # 提取列号信息
    if hasattr(e, 'column'):
        details['column'] = e.column
    elif hasattr(e, 'col'):
        details['column'] = e.col
    
    # 提取调用栈
    if hasattr(e, 'call_stack'):
        details['call_stack'] = e.call_stack
    
    # 提取错误键
    if hasattr(e, 'error_key'):
        details['error_key'] = e.error_key
    
    # 提取其他属性
    if hasattr(e, '__dict__'):
        for key, value in e.__dict__.items():
            if key not in details and not key.startswith('_'):
                details[key] = value
    
    return details


def execute_with_debug(file_path: str,
                       call_target: Optional[str] = None,
                       call_args: Optional[List] = None,
                       input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    使用调试模式执行 HPL 文件
    提供详细的执行跟踪、变量监控和性能分析
    
    Args:
        file_path: HPL文件路径
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        input_data: 可选的输入数据（用于input()函数）
    
    Returns:
        dict: 包含执行结果和调试信息
    """
    return execute_hpl(file_path, debug_mode=True, 
                      call_target=call_target, call_args=call_args, input_data=input_data)


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
