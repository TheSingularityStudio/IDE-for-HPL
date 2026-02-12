"""
沙箱执行器模块
提供资源限制的HPL代码执行环境
解决缺乏内存/CPU/文件系统限制的安全问题（P0修复）
"""

import os
import sys
import multiprocessing
import logging
import tempfile
import shutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Unix-specific modules - not available on Windows
try:
    import resource
except ImportError:
    resource = None

try:
    import signal
except ImportError:
    signal = None

# Import code processor for include file handling
from ide.services.code_processor import copy_include_files

logger = logging.getLogger(__name__)



@dataclass
class ResourceLimits:
    """资源限制配置"""
    max_memory_mb: int = 100  # 最大内存使用（MB）
    max_cpu_time: int = 10    # 最大CPU时间（秒）
    max_file_size_mb: int = 10  # 最大文件大小（MB）
    max_processes: int = 0    # 最大子进程数（0=禁止）
    max_open_files: int = 64  # 最大打开文件数
    max_stack_size_mb: int = 8  # 最大栈大小（MB）


class SandboxExecutor:
    """
    沙箱执行器
    
    在隔离环境中执行HPL代码，限制资源使用
    使用Unix资源限制（resource模块）和进程隔离
    """
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self._setup_complete = False
    
    def _setup_resource_limits(self):
        """
        设置当前进程的资源限制
        在子进程中调用
        """
        # Windows不支持Unix资源限制
        if resource is None:
            logger.warning("当前平台不支持Unix资源限制（resource模块不可用）")
            self._setup_complete = False
            return
        
        try:
            # 内存限制（地址空间）
            max_memory_bytes = self.limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_AS,
                (max_memory_bytes, max_memory_bytes)
            )
            logger.debug(f"设置内存限制: {self.limits.max_memory_mb}MB")
            
            # CPU时间限制
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (self.limits.max_cpu_time, self.limits.max_cpu_time)
            )
            logger.debug(f"设置CPU时间限制: {self.limits.max_cpu_time}秒")
            
            # 文件大小限制
            max_file_size = self.limits.max_file_size_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (max_file_size, max_file_size)
            )
            logger.debug(f"设置文件大小限制: {self.limits.max_file_size_mb}MB")
            
            # 子进程数限制
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (self.limits.max_processes, self.limits.max_processes)
            )
            logger.debug(f"设置子进程限制: {self.limits.max_processes}")
            
            # 打开文件数限制
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (self.limits.max_open_files, self.limits.max_open_files)
            )
            logger.debug(f"设置打开文件限制: {self.limits.max_open_files}")
            
            # 栈大小限制
            max_stack = self.limits.max_stack_size_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_STACK,
                (max_stack, max_stack)
            )
            logger.debug(f"设置栈大小限制: {self.limits.max_stack_size_mb}MB")
            
            # 禁用核心转储（安全考虑）
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            
            self._setup_complete = True
            
        except Exception as e:
            logger.error(f"设置资源限制失败: {e}")
            raise

    
    def _execute_target(self, file_path: str,
                       result_queue: multiprocessing.Queue,
                       call_target: Optional[str] = None,
                       call_args: Optional[List] = None,
                       debug_mode: bool = False,
                       input_data: Optional[Any] = None):
        """
        子进程执行目标
        
        Args:
            file_path: HPL文件路径
            result_queue: 结果队列
            call_target: 调用目标
            call_args: 调用参数
            debug_mode: 调试模式
            input_data: 输入数据（P1修复新增）
        """
        try:
            # 设置资源限制
            self._setup_resource_limits()
            
            # 导入并执行
            from ide.services.hpl_engine import HPLEngine
            
            engine = HPLEngine()
            
            if not engine.load_file(file_path):
                result_queue.put({
                    'success': False,
                    'error': f'无法加载文件: {file_path}',
                    'error_type': 'FileError'
                })
                return
            
            # P1修复：传递input_data
            if debug_mode:
                result = engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
            else:
                result = engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)
            
            result_queue.put(result)
            
        except MemoryError:
            logger.error("内存不足错误")
            result_queue.put({
                'success': False,
                'error': f'内存限制 exceeded: 代码使用超过 {self.limits.max_memory_mb}MB 内存',
                'error_type': 'MemoryLimitExceeded'
            })
        except Exception as e:
            logger.error(f"沙箱执行错误: {e}")
            result_queue.put({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            })
    
    def execute(self, file_path: str,
                timeout: float = 5.0,
                call_target: Optional[str] = None,
                call_args: Optional[List] = None,
                debug_mode: bool = False,
                input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        在沙箱中执行HPL文件
        
        Args:
            file_path: HPL文件路径
            timeout: 执行超时（秒）
            call_target: 调用目标函数
            call_args: 调用参数
            debug_mode: 调试模式
            input_data: 输入数据（P1修复新增）
        
        Returns:
            dict: 执行结果
        """
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'文件不存在: {file_path}',
                'error_type': 'FileNotFoundError'
            }
        
        # 检查平台支持
        if sys.platform == 'win32':
            logger.warning("Windows不支持Unix资源限制，仅使用进程隔离")
            # Windows回退到基本进程隔离
            from ide.utils.execution_utils import execute_with_process_timeout
            return execute_with_process_timeout(
                file_path, 
                timeout=timeout,
                call_target=call_target,
                call_args=call_args,
                debug_mode=debug_mode,
                input_data=input_data
            )
        
        # Unix系统使用完整沙箱
        result_queue = multiprocessing.Queue()
        
        process = multiprocessing.Process(
            target=self._execute_target,
            args=(file_path, result_queue, call_target, call_args, debug_mode, input_data),
            name='HPL-Sandbox'
        )
        
        try:
            process.start()
            logger.info(f"启动沙箱进程 (PID={process.pid}): {file_path}")
            
            # 等待完成或超时
            process.join(timeout)
            
            if process.is_alive():
                # 超时
                logger.warning(f"沙箱执行超时，终止进程 (PID={process.pid})")
                process.terminate()
                process.join(2)
                
                if process.is_alive():
                    # 强制杀死
                    try:
                        if signal is not None:
                            os.kill(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                    except:
                        pass
                    process.join(1)

                
                return {
                    'success': False,
                    'error': f'执行超时: 超过 {timeout} 秒限制',
                    'error_type': 'TimeoutError',
                    'resource_limits': {
                        'memory_mb': self.limits.max_memory_mb,
                        'cpu_time': self.limits.max_cpu_time
                    }
                }
            
            # 获取结果
            if not result_queue.empty():
                result = result_queue.get()
                
                # 添加资源限制信息
                if 'resource_limits' not in result:
                    result['resource_limits'] = {
                        'memory_mb': self.limits.max_memory_mb,
                        'cpu_time': self.limits.max_cpu_time,
                        'file_size_mb': self.limits.max_file_size_mb
                    }
                
                return result
            else:
                return {
                    'success': False,
                    'error': '沙箱进程异常退出，无结果',
                    'error_type': 'SandboxError',
                    'exit_code': process.exitcode
                }
                
        except Exception as e:
            logger.error(f"沙箱控制错误: {e}", exc_info=True)
            if process.is_alive():
                process.terminate()
                process.join(1)
            return {
                'success': False,
                'error': f'沙箱控制错误: {str(e)}',
                'error_type': type(e).__name__
            }
    
    def execute_code(self, code: str,
                    timeout: float = 5.0,
                    call_target: Optional[str] = None,
                    call_args: Optional[List] = None,
                    debug_mode: bool = False,
                    file_path: Optional[str] = None,
                    input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        在沙箱中执行HPL代码字符串
        
        Args:
            code: HPL代码字符串
            timeout: 执行超时（秒）
            call_target: 调用目标
            call_args: 调用参数
            debug_mode: 调试模式
            file_path: 可选的文件路径（用于错误显示和include路径解析）
            input_data: 输入数据（P1修复新增）
        
        Returns:
            dict: 执行结果
        """
        # 创建临时文件
        temp_dir = tempfile.mkdtemp(prefix='hpl_sandbox_')
        temp_file = os.path.join(temp_dir, 'code.hpl')
        
        try:
            # 复制 include 文件到临时目录（P2修复：解决include文件找不到的问题）
            copied_files, _, not_found = copy_include_files(
                code, temp_dir, current_file=file_path
            )
            
            if not_found:
                logger.warning(f"未找到的 include 文件: {', '.join(not_found)}")
            
            # 写入代码
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # 在沙箱中执行
            result = self.execute(
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



def execute_in_sandbox(file_path: str,
                      timeout: float = 5.0,
                      max_memory_mb: int = 100,
                      max_cpu_time: int = 10,
                      input_data: Optional[Any] = None,
                      **kwargs) -> Dict[str, Any]:
    """
    便捷函数：在沙箱中执行HPL文件
    
    Args:
        file_path: HPL文件路径
        timeout: 超时时间（秒）
        max_memory_mb: 最大内存（MB）
        max_cpu_time: 最大CPU时间（秒）
        input_data: 输入数据（P1修复新增）
        **kwargs: 其他参数
    
    Returns:
        dict: 执行结果
    """
    limits = ResourceLimits(
        max_memory_mb=max_memory_mb,
        max_cpu_time=max_cpu_time
    )
    
    sandbox = SandboxExecutor(limits)
    return sandbox.execute(file_path, timeout=timeout, input_data=input_data, **kwargs)


def execute_code_in_sandbox(code: str,
                           timeout: float = 5.0,
                           max_memory_mb: int = 100,
                           max_cpu_time: int = 10,
                           input_data: Optional[Any] = None,
                           file_path: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
    """
    便捷函数：在沙箱中执行HPL代码字符串
    
    Args:
        code: HPL代码字符串
        timeout: 超时时间（秒）
        max_memory_mb: 最大内存（MB）
        max_cpu_time: 最大CPU时间（秒）
        input_data: 输入数据（P1修复新增）
        file_path: 可选的文件路径（用于include路径解析，P2修复新增）
        **kwargs: 其他参数
    
    Returns:
        dict: 执行结果
    """
    limits = ResourceLimits(
        max_memory_mb=max_memory_mb,
        max_cpu_time=max_cpu_time
    )
    
    sandbox = SandboxExecutor(limits)
    return sandbox.execute_code(code, timeout=timeout, input_data=input_data, file_path=file_path, **kwargs)



# 默认沙箱执行器实例
_default_sandbox = None

def get_default_sandbox() -> SandboxExecutor:
    """获取默认沙箱执行器"""
    global _default_sandbox
    if _default_sandbox is None:
        _default_sandbox = SandboxExecutor()
    return _default_sandbox
