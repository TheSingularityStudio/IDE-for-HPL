"""
通用工具函数
"""
import threading
import logging

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """执行超时异常"""
    pass


def execute_with_timeout(func, timeout_sec, *args, **kwargs):
    """
    带超时的函数执行
    使用线程实现跨平台兼容
    
    Args:
        func: 要执行的函数
        timeout_sec: 超时时间（秒）
        *args, **kwargs: 传递给函数的参数
    
    Returns:
        函数执行结果
    
    Raises:
        TimeoutException: 当执行超时时
        Exception: 当函数执行抛出异常时
    """
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
        raise TimeoutException(f"代码执行超过 {timeout_sec} 秒限制")
    
    if exception[0]:
        raise exception[0]
    
    return result[0]
