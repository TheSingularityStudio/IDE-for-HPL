"""
HPL Runtime 统一管理模块
提供统一的运行时可用性检查和状态管理
解决多个模块独立实现检查导致的冗余和不一致问题
"""

import time
import logging
from typing import Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class HPLRuntimeManager:
    """
    HPL Runtime 管理器（单例模式）
    
    提供功能：
    1. 统一的运行时可用性检查
    2. 动态状态刷新（支持强制刷新）
    3. 运行时状态变更监听
    4. 详细的运行时信息获取
    """
    
    _instance: Optional['HPLRuntimeManager'] = None
    _initialized: bool = False
    
    # 配置
    CHECK_INTERVAL = 30  # 默认30秒刷新间隔
    CACHE_ENABLED = True  # 启用缓存
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, check_interval: int = 30):
        if self._initialized:
            return
            
        self._available: Optional[bool] = None
        self._last_check: float = 0
        self._check_interval = check_interval
        self._runtime_info: dict = {}
        self._listeners: list = []
        self._initialized = True
        
        logger.info("HPLRuntimeManager 初始化完成")
    
    def is_available(self, force_check: bool = False) -> bool:
        """
        检查 hpl_runtime 是否可用
        
        Args:
            force_check: 是否强制刷新检查（忽略缓存）
        
        Returns:
            bool: 运行时是否可用
        """
        now = time.time()
        
        # 判断是否需要重新检查
        need_check = (
            force_check or
            self._available is None or
            not self.CACHE_ENABLED or
            (now - self._last_check) > self._check_interval
        )
        
        if need_check:
            self._perform_check()
        
        return bool(self._available)
    
    def _perform_check(self):
        """执行实际的运行时检查"""
        try:
            import hpl_runtime
            self._available = True
            self._runtime_info = {
                'version': getattr(hpl_runtime, '__version__', 'unknown'),
                'path': getattr(hpl_runtime, '__file__', 'unknown'),
                'available': True
            }
            logger.info(f"hpl-runtime 已加载 (版本: {self._runtime_info['version']})")
        except ImportError as e:
            self._available = False
            self._runtime_info = {
                'available': False,
                'error': str(e)
            }
            logger.warning(f"hpl-runtime 未安装: {e}")
        
        self._last_check = time.time()
        
        # 通知监听器
        self._notify_listeners()
    
    def get_runtime_info(self) -> dict:
        """
        获取运行时详细信息
        
        Returns:
            dict: 包含版本、路径等信息的字典
        """
        # 确保信息是最新的
        if self._runtime_info.get('available') is None:
            self.is_available()
        return self._runtime_info.copy()
    
    def refresh(self) -> bool:
        """
        强制刷新运行时状态
        
        Returns:
            bool: 刷新后的可用性状态
        """
        return self.is_available(force_check=True)
    
    def add_listener(self, callback: Callable[[bool], None]):
        """
        添加状态变更监听器
        
        Args:
            callback: 状态变更时调用的回调函数，接收可用性状态作为参数
        """
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[bool], None]):
        """移除状态变更监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """通知所有监听器状态变更"""
        for listener in self._listeners:
            try:
                listener(self._available)
            except Exception as e:
                logger.error(f"运行时状态监听器错误: {e}")
    
    def require_runtime(self, error_msg: str = None):
        """
        装饰器：要求运行时可用
        
        用于装饰需要运行时支持的函数，如果运行时不可用则返回错误响应
        
        Args:
            error_msg: 自定义错误消息
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.is_available():
                    msg = error_msg or "hpl_runtime 不可用，无法执行操作"
                    logger.warning(msg)
                    return {
                        'success': False,
                        'error': msg,
                        'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
                    }
                return func(*args, **kwargs)
            return wrapper
        return decorator


# 便捷函数 - 保持向后兼容


def check_runtime_available(force_check: bool = False) -> bool:
    """
    检查 hpl_runtime 是否可用（便捷函数）
    
    这是原有的 check_runtime_available 函数的统一实现，
    所有模块应从此模块导入此函数。
    
    Args:
        force_check: 是否强制刷新检查
    
    Returns:
        bool: 是否可用
    """
    return HPLRuntimeManager().is_available(force_check)


def get_runtime_info() -> dict:
    """
    获取运行时详细信息（便捷函数）
    
    Returns:
        dict: 运行时信息
    """
    return HPLRuntimeManager().get_runtime_info()


def refresh_runtime_status() -> bool:
    """
    刷新运行时状态（便捷函数）
    
    Returns:
        bool: 刷新后的可用性状态
    """
    return HPLRuntimeManager().refresh()


# 全局实例获取函数
def get_runtime_manager() -> HPLRuntimeManager:
    """
    获取 HPLRuntimeManager 单例实例
    
    Returns:
        HPLRuntimeManager: 运行时管理器实例
    """
    return HPLRuntimeManager()


# 向后兼容的别名
is_runtime_available = check_runtime_available
