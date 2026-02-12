"""
"""
HPL Runtime 管理模块
提供简化的运行时可用性检查
"""

import logging

logger = logging.getLogger(__name__)


def check_runtime_available() -> bool:
    """
    检查 hpl_runtime 是否可用

    Returns:
        bool: 是否可用
    """
    try:
        import hpl_runtime
        logger.info("hpl-runtime 已加载")
        return True
    except ImportError as e:
        logger.warning(f"hpl-runtime 未安装: {e}")
        return False


def get_runtime_info() -> dict:
    """
    获取运行时信息

    Returns:
        dict: 运行时信息
    """
    try:
        import hpl_runtime
        return {
            'available': True,
            'version': getattr(hpl_runtime, '__version__', 'unknown'),
            'path': getattr(hpl_runtime, '__file__', 'unknown')
        }
    except ImportError as e:
        return {
            'available': False,
            'error': str(e)
        }


# 向后兼容的别名
is_runtime_available = check_runtime_available
