"""
临时文件管理模块
提供可靠的临时文件和目录管理
解决临时文件清理不可靠的问题（P0修复）
"""

import os
import tempfile
import shutil
import atexit
import logging
import time
import threading
from typing import Optional, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TempManager:
    """
    临时文件管理器（单例模式）
    
    功能：
    1. 创建和管理临时文件/目录
    2. 自动清理（程序退出时）
    3. 定期清理过期临时文件
    4. 上下文管理器支持
    """
    
    _instance: Optional['TempManager'] = None
    _initialized: bool = False
    _lock = threading.Lock()
    
    # 配置
    DEFAULT_PREFIX = 'hpl_'
    CLEANUP_INTERVAL = 3600  # 1小时检查一次
    MAX_AGE = 7200  # 2小时后视为过期
    AUTO_REGISTER_ATEXIT = True  # 自动注册退出清理
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, prefix: str = None, cleanup_interval: int = None):
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
                
            self._prefix = prefix or self.DEFAULT_PREFIX
            self._cleanup_interval = cleanup_interval or self.CLEANUP_INTERVAL
            self._temp_items: List[dict] = []  # 跟踪所有临时项
            self._cleanup_thread: Optional[threading.Thread] = None
            self._stop_cleanup = threading.Event()
            
            # 注册退出清理
            if self.AUTO_REGISTER_ATEXIT:
                atexit.register(self._cleanup_all)
            
            # 启动定期清理线程
            self._start_periodic_cleanup()
            
            self._initialized = True
            logger.info(f"TempManager 初始化完成 (prefix={self._prefix})")
    
    def _start_periodic_cleanup(self):
        """启动定期清理线程"""
        def cleanup_worker():
            while not self._stop_cleanup.wait(self._cleanup_interval):
                try:
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"定期清理失败: {e}")
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_worker,
            name='TempManager-Cleanup',
            daemon=True
        )
        self._cleanup_thread.start()
        logger.debug("定期清理线程已启动")
    
    def _cleanup_expired(self):
        """清理过期的临时文件"""
        current_time = time.time()
        expired_items = []
        
        with self._lock:
            for item in self._temp_items[:]:
                age = current_time - item['created_at']
                if age > self.MAX_AGE:
                    expired_items.append(item)
                    self._temp_items.remove(item)
        
        for item in expired_items:
            try:
                path = item['path']
                if os.path.exists(path):
                    if item['type'] == 'dir':
                        shutil.rmtree(path, ignore_errors=True)
                        logger.info(f"清理过期临时目录: {path}")
                    else:
                        os.remove(path)
                        logger.info(f"清理过期临时文件: {path}")
            except Exception as e:
                logger.warning(f"清理过期项失败: {e}")
    
    def _cleanup_all(self):
        """清理所有临时文件（程序退出时调用）"""
        logger.info("程序退出，清理所有临时文件...")
        
        # 停止定期清理线程
        self._stop_cleanup.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2)
        
        with self._lock:
            items = self._temp_items[:]
            self._temp_items.clear()
        
        for item in items:
            try:
                path = item['path']
                if os.path.exists(path):
                    if item['type'] == 'dir':
                        shutil.rmtree(path, ignore_errors=True)
                        logger.debug(f"清理临时目录: {path}")
                    else:
                        os.remove(path)
                        logger.debug(f"清理临时文件: {path}")
            except Exception as e:
                logger.warning(f"清理失败: {e}")
        
        logger.info("临时文件清理完成")
    
    def create_temp_dir(self, suffix: str = '', 
                        prefix: str = None,
                        register: bool = True) -> str:
        """
        创建临时目录
        
        Args:
            suffix: 后缀
            prefix: 前缀（默认使用配置）
            register: 是否注册到管理器（自动清理）
        
        Returns:
            str: 临时目录路径
        """
        prefix = prefix or self._prefix
        temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
        
        if register:
            with self._lock:
                self._temp_items.append({
                    'path': temp_dir,
                    'type': 'dir',
                    'created_at': time.time()
                })
            logger.debug(f"创建并注册临时目录: {temp_dir}")
        else:
            logger.debug(f"创建临时目录（未注册）: {temp_dir}")
        
        return temp_dir
    
    def create_temp_file(self, suffix: str = '.tmp',
                         prefix: str = None,
                         register: bool = True,
                         mode: str = 'w',
                         encoding: str = 'utf-8') -> tuple:
        """
        创建临时文件
        
        Args:
            suffix: 后缀
            prefix: 前缀（默认使用配置）
            register: 是否注册到管理器
            mode: 文件打开模式
            encoding: 编码
        
        Returns:
            tuple: (文件路径, 文件对象)
        """
        prefix = prefix or self._prefix
        
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        
        try:
            # 转换为文件对象
            file_obj = os.fdopen(fd, mode, encoding=encoding)
            
            if register:
                with self._lock:
                    self._temp_items.append({
                        'path': temp_path,
                        'type': 'file',
                        'created_at': time.time()
                    })
                logger.debug(f"创建并注册临时文件: {temp_path}")
            else:
                logger.debug(f"创建临时文件（未注册）: {temp_path}")
            
            return temp_path, file_obj
            
        except Exception:
            # 如果失败，确保关闭并删除
            try:
                os.close(fd)
                os.remove(temp_path)
            except:
                pass
            raise
    
    def register_path(self, path: str, item_type: str = 'file'):
        """
        手动注册路径到管理器
        
        Args:
            path: 路径
            item_type: 类型 ('file' 或 'dir')
        """
        with self._lock:
            self._temp_items.append({
                'path': path,
                'type': item_type,
                'created_at': time.time()
            })
        logger.debug(f"注册路径到管理器: {path}")
    
    def unregister_path(self, path: str):
        """
        从管理器移除路径（不删除文件）
        
        Args:
            path: 路径
        """
        with self._lock:
            self._temp_items = [
                item for item in self._temp_items 
                if item['path'] != path
            ]
        logger.debug(f"从管理器移除路径: {path}")
    
    def cleanup_path(self, path: str):
        """
        立即清理指定路径
        
        Args:
            path: 路径
        """
        # 先取消注册
        self.unregister_path(path)
        
        # 然后删除
        try:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    logger.info(f"清理临时目录: {path}")
                else:
                    os.remove(path)
                    logger.info(f"清理临时文件: {path}")
        except Exception as e:
            logger.warning(f"清理路径失败: {path}, 错误: {e}")
    
    def get_registered_count(self) -> int:
        """获取已注册的临时项数量"""
        with self._lock:
            return len(self._temp_items)
    
    def force_cleanup_all(self):
        """强制清理所有临时文件"""
        self._cleanup_all()


# 上下文管理器支持
@contextmanager
def temp_directory(suffix: str = '', prefix: str = None, 
                   register: bool = True):
    """
    临时目录上下文管理器
    
    Args:
        suffix: 后缀
        prefix: 前缀
        register: 是否注册到管理器
    
    Yields:
        str: 临时目录路径
    
    Example:
        with temp_directory() as temp_dir:
            # 使用临时目录
            file_path = os.path.join(temp_dir, 'test.hpl')
            # 目录会在退出上下文时自动清理
    """
    manager = TempManager()
    temp_dir = None
    
    try:
        temp_dir = manager.create_temp_dir(suffix, prefix, register)
        yield temp_dir
    finally:
        if temp_dir:
            manager.cleanup_path(temp_dir)


@contextmanager
def temp_file(suffix: str = '.tmp', prefix: str = None,
              register: bool = True, mode: str = 'w',
              encoding: str = 'utf-8', delete: bool = True):
    """
    临时文件上下文管理器
    
    Args:
        suffix: 后缀
        prefix: 前缀
        register: 是否注册到管理器
        mode: 文件打开模式
        encoding: 编码
        delete: 退出时是否删除
    
    Yields:
        tuple: (文件路径, 文件对象)
    
    Example:
        with temp_file(suffix='.hpl') as (path, f):
            f.write('code...')
            f.flush()
            # 文件会在退出上下文时自动清理（如果 delete=True）
    """
    manager = TempManager()
    temp_path = None
    file_obj = None
    
    try:
        temp_path, file_obj = manager.create_temp_file(
            suffix, prefix, register, mode, encoding
        )
        yield temp_path, file_obj
    finally:
        if file_obj:
            try:
                file_obj.close()
            except:
                pass
        
        if temp_path and delete:
            manager.cleanup_path(temp_path)


# 便捷函数
def get_temp_manager() -> TempManager:
    """获取 TempManager 单例实例"""
    return TempManager()


def create_temp_dir(suffix: str = '', prefix: str = None) -> str:
    """便捷函数：创建临时目录"""
    return TempManager().create_temp_dir(suffix, prefix)


def cleanup_all_temp():
    """便捷函数：清理所有临时文件"""
    TempManager().force_cleanup_all()


# 向后兼容
TemporaryDirectory = temp_directory
TemporaryFile = temp_file
