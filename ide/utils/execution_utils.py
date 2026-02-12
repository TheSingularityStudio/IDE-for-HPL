"""
执行工具模块
提供进程隔离的执行和超时控制
解决线程超时无法终止HPL运行时的问题（P0修复）
"""

import os
import sys
import multiprocessing
import logging
import time
import signal
from typing import Dict, Any, Optional, List, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ExecutionTimeoutError(Exception):
    """执行超时异常"""
    pass


class ExecutionKilledError(Exception):
    """执行被强制终止异常"""
    pass


def _execute_in_process(file_path: str, 
                       result_queue: multiprocessing.Queue,
                       error_queue: multiprocessing.Queue,
                       call_target: Optional[str] = None,
                       call_args: Optional[List] = None,
                       debug_mode: bool = False):
    """
    在独立进程中执行HPL代码
    
    这是子进程的目标函数，在主进程中被调用
    """
    try:
        # 在子进程中导入，避免影响主进程
        from ide.services.hpl_engine import HPLEngine
        
        engine = HPLEngine()
        
        if not engine.load_file(file_path):
            result_queue.put({
                'success': False,
                'error': f'无法加载文件: {file_path}'
            })
            return
        
        if debug_mode:
            result = engine.debug(call_target=call_target, call_args=call_args)
        else:
            result = engine.execute(call_target=call_target, call_args=call_args)
        
        result_queue.put(result)
        
    except Exception as e:
        error_queue.put({
            'type': type(e).__name__,
            'message': str(e),
            'args': getattr(e, 'args', ())
        })


def execute_with_process_timeout(file_path: str,
                                 timeout: float = 5.0,
                                 call_target: Optional[str] = None,
                                 call_args: Optional[List] = None,
                                 debug_mode: bool = False) -> Dict[str, Any]:
    """
    使用进程隔离执行HPL代码，带超时控制
    
    这是P0修复的核心函数，使用multiprocessing实现真正的进程级超时
    
    Args:
        file_path: HPL文件路径
        timeout: 超时时间（秒）
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        debug_mode: 是否启用调试模式
    
    Returns:
        dict: 执行结果
    """
    if not os.path.exists(file_path):
        return {
            'success': False,
            'error': f'文件不存在: {file_path}'
        }
    
    # 创建进程间通信队列
    result_queue = multiprocessing.Queue()
    error_queue = multiprocessing.Queue()
    
    # 创建子进程
    process = multiprocessing.Process(
        target=_execute_in_process,
        args=(file_path, result_queue, error_queue, call_target, call_args, debug_mode),
        name='HPL-Executor'
    )
    
    start_time = time.time()
    
    try:
        # 启动子进程
        process.start()
        logger.info(f"启动执行进程 (PID={process.pid}): {file_path}")
        
        # 等待进程完成或超时
        process.join(timeout)
        
        # 检查是否超时
        if process.is_alive():
            # 超时，需要终止进程
            logger.warning(f"执行超时 ({timeout}秒)，终止进程 (PID={process.pid})")
            
            # 先尝试优雅终止
            process.terminate()
            process.join(2)  # 等待2秒
            
            # 如果还在运行，强制杀死
            if process.is_alive():
                logger.error(f"进程未响应，强制杀死 (PID={process.pid})")
                if sys.platform != 'win32':
                    # Unix系统使用SIGKILL
                    try:
                        os.kill(process.pid, signal.SIGKILL)
                    except:
                        pass
                else:
                    # Windows使用kill
                    process.kill()
                process.join(1)
            
            return {
                'success': False,
                'error': f'执行超时: 代码运行超过 {timeout} 秒限制',
                'error_type': 'TimeoutError',
                'execution_time': timeout
            }
        
        # 检查执行时间
        execution_time = time.time() - start_time
        
        # 检查是否有错误
        if not error_queue.empty():
            error_info = error_queue.get()
            logger.error(f"执行进程错误: {error_info}")
            return {
                'success': False,
                'error': f"执行错误: {error_info['message']}",
                'error_type': error_info['type'],
                'execution_time': execution_time
            }
        
        # 获取结果
        if not result_queue.empty():
            result = result_queue.get()
            result['execution_time'] = execution_time
            logger.info(f"执行完成，耗时: {execution_time:.2f}秒")
            return result
        else:
            # 没有结果也没有错误，可能是进程异常退出
            exit_code = process.exitcode
            logger.error(f"进程异常退出，exitcode={exit_code}")
            return {
                'success': False,
                'error': f'执行进程异常退出 (exitcode={exit_code})',
                'error_type': 'ProcessError',
                'execution_time': execution_time
            }
            
    except Exception as e:
        logger.error(f"执行控制错误: {e}", exc_info=True)
        # 确保进程被终止
        if process.is_alive():
            process.terminate()
            process.join(1)
        return {
            'success': False,
            'error': f'执行控制错误: {str(e)}',
            'error_type': type(e).__name__
        }


def execute_code_with_timeout(code: str,
                              timeout: float = 5.0,
                              call_target: Optional[str] = None,
                              call_args: Optional[List] = None,
                              debug_mode: bool = False,
                              file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    执行HPL代码字符串，带超时控制
    
    Args:
        code: HPL代码字符串
        timeout: 超时时间（秒）
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        debug_mode: 是否启用调试模式
        file_path: 可选的文件路径（用于错误显示）
    
    Returns:
        dict: 执行结果
    """
    import tempfile
    import os
    
    # 创建临时文件
    temp_dir = tempfile.mkdtemp(prefix='hpl_exec_')
    temp_file = os.path.join(temp_dir, 'temp_code.hpl')
    
    try:
        # 写入代码到临时文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 使用进程隔离执行
        result = execute_with_process_timeout(
            temp_file, 
            timeout=timeout,
            call_target=call_target,
            call_args=call_args,
            debug_mode=debug_mode
        )
        
        return result
        
    finally:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


@contextmanager
def execution_timeout(timeout: float, 
                     on_timeout: Optional[Callable] = None):
    """
    执行超时上下文管理器（用于同步代码块）
    
    注意：这使用信号实现，只在Unix系统上有效
    对于Windows，建议使用 execute_with_process_timeout
    
    Args:
        timeout: 超时时间（秒）
        on_timeout: 超时时的回调函数
    
    Example:
        with execution_timeout(5.0):
            # 执行可能耗时的操作
            result = long_running_operation()
    """
    if sys.platform == 'win32':
        # Windows不支持信号超时，使用进程版本
        logger.warning("Windows系统不支持信号超时，请使用 execute_with_process_timeout")
        yield
        return
    
    def timeout_handler(signum, frame):
        if on_timeout:
            on_timeout()
        raise ExecutionTimeoutError(f"执行超时（{timeout}秒）")
    
    # 设置信号处理器
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(timeout))
    
    try:
        yield
    finally:
        # 恢复信号处理器
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def check_process_resources(process: multiprocessing.Process,
                            max_memory_mb: int = 100,
                            max_cpu_percent: float = 90.0) -> Dict[str, Any]:
    """
    检查进程资源使用情况
    
    Args:
        process: 进程对象
        max_memory_mb: 最大内存限制（MB）
        max_cpu_percent: 最大CPU使用率限制（%）
    
    Returns:
        dict: 资源使用情况
    """
    try:
        import psutil
        
        if not process.is_alive():
            return {'alive': False}
        
        proc = psutil.Process(process.pid)
        
        # 获取内存使用
        memory_info = proc.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        # 获取CPU使用
        cpu_percent = proc.cpu_percent(interval=0.1)
        
        result = {
            'alive': True,
            'pid': process.pid,
            'memory_mb': memory_mb,
            'memory_percent': proc.memory_percent(),
            'cpu_percent': cpu_percent,
            'memory_limit_exceeded': memory_mb > max_memory_mb,
            'cpu_limit_exceeded': cpu_percent > max_cpu_percent
        }
        
        return result
        
    except ImportError:
        return {
            'alive': process.is_alive(),
            'pid': process.pid,
            'error': 'psutil not available'
        }
    except Exception as e:
        return {
            'alive': process.is_alive(),
            'error': str(e)
        }


# 便捷函数
def execute_hpl_safe(file_path: str,
                    timeout: float = 5.0,
                    **kwargs) -> Dict[str, Any]:
    """
    安全执行HPL文件的便捷函数
    
    Args:
        file_path: HPL文件路径
        timeout: 超时时间（秒）
        **kwargs: 传递给 execute_with_process_timeout 的其他参数
    
    Returns:
        dict: 执行结果
    """
    return execute_with_process_timeout(file_path, timeout=timeout, **kwargs)


def execute_hpl_code_safe(code: str,
                         timeout: float = 5.0,
                         **kwargs) -> Dict[str, Any]:
    """
    安全执行HPL代码字符串的便捷函数
    
    Args:
        code: HPL代码字符串
        timeout: 超时时间（秒）
        **kwargs: 传递给 execute_code_with_timeout 的其他参数
    
    Returns:
        dict: 执行结果
    """
    return execute_code_with_timeout(code, timeout=timeout, **kwargs)


# 向后兼容
execute_with_timeout = execute_with_process_timeout
TimeoutException = ExecutionTimeoutError
