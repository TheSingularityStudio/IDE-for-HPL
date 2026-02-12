"""
通用工具模块
合并了执行工具、助手函数和临时文件管理
"""

import os
import sys
import multiprocessing
import logging
import time
import signal
import tempfile
import shutil
import atexit
from typing import Dict, Any, Optional, List, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ExecutionTimeoutError(Exception):
    """执行超时异常"""
    pass


class ExecutionKilledError(Exception):
    """执行被强制终止异常"""
    pass


def execute_with_process_timeout(file_path: str,
                                 timeout: float = 5.0,
                                 call_target: Optional[str] = None,
                                 call_args: Optional[List] = None,
                                 debug_mode: bool = False,
                                 input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    使用进程隔离执行HPL代码，带超时控制

    Args:
        file_path: HPL文件路径
        timeout: 超时时间（秒）
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        debug_mode: 是否启用调试模式
        input_data: 可选的输入数据

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
        args=(file_path, result_queue, error_queue, call_target, call_args, debug_mode, input_data),
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


def _execute_in_process(file_path: str,
                       result_queue: multiprocessing.Queue,
                       error_queue: multiprocessing.Queue,
                       call_target: Optional[str] = None,
                       call_args: Optional[List] = None,
                       debug_mode: bool = False,
                       input_data: Optional[Any] = None):
    """
    在独立进程中执行HPL代码
    """
    try:
        # 在子进程中导入，避免影响主进程
        from ide.services.execution_service import HPLExecutionService

        service = HPLExecutionService()
        result = service.execute_file(file_path, call_target, call_args, debug_mode, input_data)
        result_queue.put(result)

    except Exception as e:
        error_queue.put({
            'type': type(e).__name__,
            'message': str(e),
            'args': getattr(e, 'args', ())
        })


def execute_code_with_timeout(code: str,
                              timeout: float = 5.0,
                              call_target: Optional[str] = None,
                              call_args: Optional[List] = None,
                              debug_mode: bool = False,
                              file_path: Optional[str] = None,
                              input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    执行HPL代码字符串，带超时控制

    Args:
        code: HPL代码字符串
        timeout: 超时时间（秒）
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
        debug_mode: 是否启用调试模式
        file_path: 可选的文件路径
        input_data: 可选的输入数据

    Returns:
        dict: 执行结果
    """
    import tempfile

    # 创建临时文件
    temp_dir = tempfile.mkdtemp(prefix='hpl_exec_')
    temp_file = os.path.join(temp_dir, 'temp_code.hpl')

    try:
        # 复制 include 文件到临时目录
        from ide.services.code_service import copy_include_files
        copied_files, _, not_found = copy_include_files(
            code, temp_dir, current_file=file_path
        )

        if not_found:
            logger.warning(f"未找到的 include 文件: {', '.join(not_found)}")

        # 写入代码到临时文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # 使用进程隔离执行
        result = execute_with_process_timeout(
            temp_file,
            timeout=timeout,
            call_target=call_target,
            call_args=call_args,
            debug_mode=debug_mode,
            input_data=input_data
        )

        return result

    finally:
        # 清理临时文件
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


@contextmanager
def temp_directory(prefix: str = 'hpl_'):
    """
    临时目录上下文管理器

    Args:
        prefix: 临时目录前缀

    Yields:
        str: 临时目录路径
    """
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    try:
        yield temp_dir
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


def execute_with_timeout(func, timeout_sec, *args, **kwargs):
    """
    带超时的函数执行（线程实现）

    Args:
        func: 要执行的函数
        timeout_sec: 超时时间（秒）
        *args, **kwargs: 传递给函数的参数

    Returns:
        函数执行结果

    Raises:
        ExecutionTimeoutError: 当执行超时时
    """
    import threading

    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_sec)

    if thread.is_alive():
        logger.warning(f"代码执行超时（{timeout_sec}秒）")
        raise ExecutionTimeoutError(f"代码执行超过 {timeout_sec} 秒限制")

    if exception[0]:
        raise exception[0]

    return result[0]


# 便捷函数
def execute_hpl_safe(file_path: str,
                    timeout: float = 5.0,
                    input_data: Optional[Any] = None,
                    **kwargs) -> Dict[str, Any]:
    """
    安全执行HPL文件的便捷函数

    Args:
        file_path: HPL文件路径
        timeout: 超时时间（秒）
        input_data: 可选的输入数据
        **kwargs: 其他参数

    Returns:
        dict: 执行结果
    """
    return execute_with_process_timeout(file_path, timeout=timeout, input_data=input_data, **kwargs)


def execute_hpl_code_safe(code: str,
                         timeout: float = 5.0,
                         input_data: Optional[Any] = None,
                         **kwargs) -> Dict[str, Any]:
    """
    安全执行HPL代码字符串的便捷函数

    Args:
        code: HPL代码字符串
        timeout: 超时时间（秒）
        input_data: 可选的输入数据
        **kwargs: 其他参数

    Returns:
        dict: 执行结果
    """
    return execute_code_with_timeout(code, timeout=timeout, input_data=input_data, **kwargs)


# 向后兼容
execute_with_timeout_old = execute_with_timeout
TimeoutException = ExecutionTimeoutError
