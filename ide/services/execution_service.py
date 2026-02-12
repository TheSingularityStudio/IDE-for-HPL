"""
HPL 执行服务
统一处理 HPL 代码的执行、调试和沙箱运行
合并了原有的 code_executor、hpl_engine、debug_service 和 sandbox_executor
"""

import os
import sys
import tempfile
import shutil
import logging
import hashlib
import pickle
import io
import contextlib
import multiprocessing
import queue
import threading
from typing import Dict, List, Any, Optional, Tuple, Generator
from dataclasses import dataclass, field

# 导入代码处理和安全模块
from ide.services.code_service import copy_include_files, validate_path, is_safe_filename
from ide.services.runtime_manager import check_runtime_available

# Unix-specific modules for sandboxing
try:
    import resource
except ImportError:
    resource = None

try:
    import signal
except ImportError:
    signal = None

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """资源限制配置"""
    max_memory_mb: int = 100
    max_cpu_time: int = 10
    max_file_size_mb: int = 10


@dataclass
class Breakpoint:
    """断点信息"""
    line: int
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0


@dataclass
class ExecutionTraceEntry:
    """执行跟踪条目"""
    event_type: str
    line: Optional[int]
    details: Dict[str, Any]
    timestamp: float


class ParseCache:
    """解析结果缓存"""

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '.cache')
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, code: str) -> str:
        return hashlib.md5(code.encode('utf-8')).hexdigest()

    def get(self, code: str) -> Optional[Tuple]:
        cache_key = self._get_cache_key(code)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pickle")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.debug(f"读取缓存失败: {e}")
        return None

    def set(self, code: str, parse_result: Tuple):
        cache_key = self._get_cache_key(code)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pickle")

        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(parse_result, f)
        except Exception as e:
            logger.debug(f"写入缓存失败: {e}")


class HPLEngine:
    """
    HPL 引擎
    统一封装 hpl_runtime 的功能
    """

    def __init__(self, use_cache: bool = True):
        self.current_file: Optional[str] = None
        self.source_code: Optional[str] = None
        self._parser = None
        self._parse_result: Optional[Tuple] = None
        self._cache = ParseCache() if use_cache else None
        self._runtime_available = check_runtime_available()

        if not self._runtime_available:
            raise ImportError("hpl_runtime 不可用")

    def load_file(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.source_code = f.read()
            self.current_file = file_path
            self._parse_result = None
            return True
        except Exception as e:
            logger.error(f"加载文件失败: {e}")
            return False

    def load_code(self, code: str, file_path: Optional[str] = None):
        self.source_code = code
        self.current_file = file_path or "<memory>"
        self._parse_result = None

    def _parse(self) -> Optional[Tuple]:
        if self._parse_result is not None:
            return self._parse_result

        if not self.source_code:
            return None

        # 检查缓存
        if self._cache:
            cached = self._cache.get(self.source_code)
            if cached:
                self._parse_result = cached
                return cached

        # 创建临时文件进行解析
        temp_dir = tempfile.mkdtemp(prefix='hpl_parse_')
        temp_file = os.path.join(temp_dir, 'temp_code.hpl')

        try:
            # 复制include文件
            copied_files, _, not_found = copy_include_files(
                self.source_code, temp_dir, current_file=temp_file, original_file=self.current_file
            )

            if not_found:
                logger.warning(f"解析时未找到的include文件: {', '.join(not_found)}")

            # 写入代码
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(self.source_code)

            from hpl_runtime import HPLParser
            parser = HPLParser(temp_file)
            result = parser.parse()
            self._parse_result = result

            # 缓存结果
            if self._cache:
                self._cache.set(self.source_code, result)

            return result

        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

    def validate(self) -> List[Dict[str, Any]]:
        diagnostics = []

        if not self.source_code:
            diagnostics.append({
                'line': 1, 'column': 1, 'severity': 'error',
                'message': "代码为空", 'code': None
            })
            return diagnostics

        try:
            from hpl_runtime import HPLSyntaxError, HPLImportError, format_error_for_user

            self._parse()

        except HPLSyntaxError as e:
            user_message = format_error_for_user(e, self.source_code)
            diagnostics.append({
                'line': e.line or 1,
                'column': e.column or 1,
                'severity': 'error',
                'message': user_message,
                'code': self._get_code_at_line(e.line) if e.line else None,
                'error_key': getattr(e, 'error_key', None)
            })

        except HPLImportError as e:
            diagnostics.append({
                'line': getattr(e, 'line', 1),
                'column': getattr(e, 'column', 1),
                'severity': 'warning',
                'message': f"导入警告: {str(e)}",
                'code': None
            })

        except Exception as e:
            diagnostics.append({
                'line': 1, 'column': 1, 'severity': 'error',
                'message': f"验证错误: {str(e)}", 'code': None
            })

        return diagnostics

    def get_completions(self, line: int, column: int, prefix: str = "") -> List[Dict[str, Any]]:
        items = []

        parse_result = self._parse()
        if not parse_result:
            return items

        classes, objects, functions, main_func, _, _, _ = parse_result

        # 类名补全
        for class_name, hpl_class in classes.items():
            if class_name.startswith(prefix):
                methods = []
                if hasattr(hpl_class, 'methods'):
                    methods = list(hpl_class.methods.keys())

                items.append({
                    'label': class_name,
                    'kind': 'Class',
                    'detail': f"Class: {class_name}",
                    'documentation': f"类 {class_name}" + (f"\n方法: {', '.join(methods)}" if methods else ""),
                    'insertText': class_name
                })

        # 函数补全
        for func_name, func in functions.items():
            if func_name.startswith(prefix):
                params = getattr(func, 'params', [])
                param_snippets = [f"${{{i+1}:{param}}}" for i, param in enumerate(params)]
                insert_text = f"{func_name}({', '.join(param_snippets)})"

                items.append({
                    'label': func_name,
                    'kind': 'Function',
                    'detail': f"Function: {func_name}({', '.join(params)})",
                    'documentation': f"函数 {func_name}" + (f"\n参数: {', '.join(params)}" if params else ""),
                    'insertText': insert_text,
                    'params': params
                })

        # main 函数
        if main_func and 'main'.startswith(prefix):
            params = getattr(main_func, 'params', [])
            param_snippets = [f"${{{i+1}:{param}}}" for i, param in enumerate(params)]
            insert_text = f"main({', '.join(param_snippets)})"

            items.insert(0, {
                'label': 'main',
                'kind': 'Function',
                'detail': f"Function: main({', '.join(params)})",
                'documentation': "主函数" + (f"\n参数: {', '.join(params)}" if params else ""),
                'insertText': insert_text,
                'params': params,
                'is_main': True
            })

        items.sort(key=lambda x: x['label'])
        return items

    def execute(self, call_target: Optional[str] = None,
                call_args: Optional[List] = None,
                input_data: Optional[Any] = None) -> Dict[str, Any]:
        parse_result = self._parse()
        if not parse_result:
            return {'success': False, 'error': '解析失败，无法执行'}

        classes, objects, functions, main_func, _, _, _ = parse_result

        if not main_func and not call_target:
            return {'success': False, 'error': '没有 main 函数或 call 目标'}

        # 处理输入数据
        stdin_buffer = None
        original_stdin = None
        if input_data is not None:
            if isinstance(input_data, list):
                input_data = '\n'.join(str(item) for item in input_data)
            stdin_buffer = io.StringIO(str(input_data))
            original_stdin = sys.stdin

        try:
            from hpl_runtime import HPLEvaluator, HPLRuntimeError, format_error_for_user

            output_buffer = io.StringIO()

            if stdin_buffer:
                sys.stdin = stdin_buffer

            with contextlib.redirect_stdout(output_buffer):
                evaluator = HPLEvaluator(
                    classes=classes,
                    objects=objects,
                    functions=functions,
                    main_func=main_func,
                    call_target=call_target,
                    call_args=call_args or []
                )
                evaluator.run()

            return {
                'success': True,
                'output': output_buffer.getvalue()
            }

        except HPLRuntimeError as e:
            user_message = format_error_for_user(e, self.source_code)
            return {
                'success': False,
                'error': user_message,
                'error_type': type(e).__name__,
                'line': getattr(e, 'line', None),
                'column': getattr(e, 'column', None),
                'call_stack': getattr(e, 'call_stack', []),
                'error_key': getattr(e, 'error_key', None)
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"执行错误: {str(e)}",
                'error_type': type(e).__name__
            }
        finally:
            if original_stdin is not None:
                sys.stdin = original_stdin

    def debug(self, call_target: Optional[str] = None,
              call_args: Optional[List] = None,
              input_data: Optional[Any] = None) -> Dict[str, Any]:
        temp_file = None
        temp_dir = None
        file_to_debug = None

        try:
            if not self.current_file or self.current_file == "<memory>":
                temp_dir = tempfile.mkdtemp(prefix='hpl_debug_')
                temp_file = os.path.join(temp_dir, 'debug_temp.hpl')

                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(self.source_code or "")

                file_to_debug = temp_file
            else:
                file_to_debug = self.current_file

            return self._debug_file(file_to_debug, call_target, call_args, input_data)

        except Exception as e:
            logger.error(f"调试准备失败: {e}")
            return {
                'success': False,
                'error': f"调试准备失败: {str(e)}",
                'debug_info': {}
            }
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {temp_file}, 错误: {e}")

            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {temp_dir}, 错误: {e}")

    def _debug_file(self, file_path: str, call_target: Optional[str] = None,
                    call_args: Optional[List] = None,
                    input_data: Optional[Any] = None) -> Dict[str, Any]:
        stdin_buffer = None
        original_stdin = None
        if input_data is not None:
            if isinstance(input_data, list):
                input_data = '\n'.join(str(item) for item in input_data)
            stdin_buffer = io.StringIO(str(input_data))
            original_stdin = sys.stdin

        try:
            from hpl_runtime import DebugInterpreter, HPLSyntaxError, HPLRuntimeError

            if stdin_buffer:
                sys.stdin = stdin_buffer

            interpreter = DebugInterpreter(debug_mode=True, verbose=True)
            result = interpreter.run(file_path, call_target=call_target, call_args=call_args)

            debug_info = result.get('debug_info', {})

            formatted_result = {
                'success': result.get('success', False),
                'error': str(result.get('error')) if result.get('error') else None,
                'line': getattr(result.get('error'), 'line', None),
                'column': getattr(result.get('error'), 'column', None),
                'debug_info': {
                    'execution_trace': debug_info.get('execution_trace', []),
                    'variable_snapshots': debug_info.get('variable_snapshots', []),
                    'call_stack_history': debug_info.get('call_stack_history', []),
                    'report': debug_info.get('report', '')
                }
            }

            snapshots = debug_info.get('variable_snapshots', [])
            if snapshots:
                formatted_result['final_variables'] = snapshots[-1]

            formatted_result['function_stats'] = self._calculate_function_stats(
                debug_info.get('execution_trace', [])
            )

            return formatted_result

        except HPLSyntaxError as e:
            from hpl_runtime import format_error_for_user
            return {
                'success': False,
                'error': format_error_for_user(e, self.source_code),
                'line': e.line,
                'column': e.column,
                'error_key': getattr(e, 'error_key', None),
                'debug_info': {}
            }

        except HPLRuntimeError as e:
            from hpl_runtime import format_error_for_user
            return {
                'success': False,
                'error': format_error_for_user(e, self.source_code),
                'line': getattr(e, 'line', None),
                'column': getattr(e, 'column', None),
                'call_stack': getattr(e, 'call_stack', []),
                'error_key': getattr(e, 'error_key', None),
                'debug_info': {}
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"调试失败: {str(e)}",
                'debug_info': {}
            }
        finally:
            if original_stdin is not None:
                sys.stdin = original_stdin

    def _calculate_function_stats(self, execution_trace: List[Dict]) -> Dict[str, Dict[str, Any]]:
        stats = {}
        current_function = None
        function_start_time = None

        for entry in execution_trace:
            event_type = entry.get('type')
            timestamp = entry.get('timestamp', 0)
            details = entry.get('details', {})

            if event_type == 'FUNCTION_CALL':
                func_name = details.get('name')
                if func_name:
                    current_function = func_name
                    function_start_time = timestamp

                    if func_name not in stats:
                        stats[func_name] = {
                            'calls': 0,
                            'total_time': 0,
                            'min_time': float('inf'),
                            'max_time': 0
                        }
                    stats[func_name]['calls'] += 1

            elif event_type == 'FUNCTION_RETURN' and current_function:
                duration = timestamp - function_start_time if function_start_time else 0
                func_stats = stats[current_function]
                func_stats['total_time'] += duration
                func_stats['min_time'] = min(func_stats['min_time'], duration)
                func_stats['max_time'] = max(func_stats['max_time'], duration)

                current_function = None
                function_start_time = None

        for func_name, func_stats in stats.items():
            if func_stats['calls'] > 0:
                func_stats['avg_time'] = func_stats['total_time'] / func_stats['calls']
            if func_stats['min_time'] == float('inf'):
                func_stats['min_time'] = 0

        return stats

    def get_code_outline(self) -> Dict[str, List[Dict[str, Any]]]:
        outline = {'classes': [], 'functions': [], 'objects': [], 'imports': []}

        parse_result = self._parse()
        if not parse_result:
            return outline

        classes, objects, functions, main_func, _, _, imports = parse_result

        for class_name, hpl_class in classes.items():
            methods = []
            if hasattr(hpl_class, 'methods'):
                methods = list(hpl_class.methods.keys())

            parent = None
            if hasattr(hpl_class, 'parent') and hpl_class.parent:
                parent = hpl_class.parent.name if hasattr(hpl_class.parent, 'name') else str(hpl_class.parent)

            outline['classes'].append({
                'name': class_name,
                'parent': parent,
                'methods': methods
            })

        for func_name, func in functions.items():
            params = getattr(func, 'params', [])
            outline['functions'].append({
                'name': func_name,
                'params': params
            })

        if main_func:
            params = getattr(main_func, 'params', [])
            outline['functions'].insert(0, {
                'name': 'main',
                'params': params,
                'is_main': True
            })

        for obj_name, obj in objects.items():
            class_name = "Unknown"
            if hasattr(obj, 'hpl_class') and hasattr(obj.hpl_class, 'name'):
                class_name = obj.hpl_class.name

            outline['objects'].append({
                'name': obj_name,
                'class': class_name
            })

        for imp in imports:
            module = imp.get('module', '')
            alias = imp.get('alias', module)
            outline['imports'].append({
                'module': module,
                'alias': alias
            })

        return outline

    def _get_code_at_line(self, line_num: Optional[int]) -> Optional[str]:
        if not line_num or line_num < 1 or not self.source_code:
            return None

        lines = self.source_code.split('\n')
        if line_num <= len(lines):
            return lines[line_num - 1]
        return None


class SandboxExecutor:
    """
    沙箱执行器
    在隔离环境中执行HPL代码，限制资源使用
    """

    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self._setup_complete = False

    def _setup_resource_limits(self):
        if resource is None:
            logger.warning("当前平台不支持Unix资源限制")
            self._setup_complete = False
            return

        try:
            max_memory_bytes = self.limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))

            resource.setrlimit(resource.RLIMIT_CPU, (self.limits.max_cpu_time, self.limits.max_cpu_time))

            max_file_size = self.limits.max_file_size_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_size, max_file_size))

            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

            self._setup_complete = True

        except Exception as e:
            logger.error(f"设置资源限制失败: {e}")
            raise

    def _execute_target(self, file_path: str, result_queue: multiprocessing.Queue,
                       call_target: Optional[str] = None, call_args: Optional[List] = None,
                       debug_mode: bool = False, input_data: Optional[Any] = None):
        try:
            self._setup_resource_limits()

            engine = HPLEngine()
            if not engine.load_file(file_path):
                result_queue.put({
                    'success': False,
                    'error': f'无法加载文件: {file_path}',
                    'error_type': 'FileError'
                })
                return

            if debug_mode:
                result = engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
            else:
                result = engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)

            result_queue.put(result)

        except MemoryError:
            result_queue.put({
                'success': False,
                'error': f'内存限制 exceeded: 代码使用超过 {self.limits.max_memory_mb}MB 内存',
                'error_type': 'MemoryLimitExceeded'
            })
        except Exception as e:
            result_queue.put({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            })

    def execute(self, file_path: str, timeout: float = 5.0,
                call_target: Optional[str] = None, call_args: Optional[List] = None,
                debug_mode: bool = False, input_data: Optional[Any] = None) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'文件不存在: {file_path}',
                'error_type': 'FileNotFoundError'
            }

        if sys.platform == 'win32':
            logger.warning("Windows不支持Unix资源限制，仅使用进程隔离")
            # Windows fallback
            return self._execute_direct(file_path, call_target, call_args, debug_mode, input_data)

        result_queue = multiprocessing.Queue()

        process = multiprocessing.Process(
            target=self._execute_target,
            args=(file_path, result_queue, call_target, call_args, debug_mode, input_data),
            name='HPL-Sandbox'
        )

        try:
            process.start()
            process.join(timeout)

            if process.is_alive():
                process.terminate()
                process.join(2)

                if process.is_alive():
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
                    'error_type': 'TimeoutError'
                }

            if not result_queue.empty():
                result = result_queue.get()
                return result
            else:
                return {
                    'success': False,
                    'error': '沙箱进程异常退出，无结果',
                    'error_type': 'SandboxError'
                }

        except Exception as e:
            if process.is_alive():
                process.terminate()
                process.join(1)
            return {
                'success': False,
                'error': f'沙箱控制错误: {str(e)}',
                'error_type': type(e).__name__
            }

    def _execute_direct(self, file_path: str, call_target: Optional[str] = None,
                       call_args: Optional[List] = None, debug_mode: bool = False,
                       input_data: Optional[Any] = None) -> Dict[str, Any]:
        """Windows下的直接执行"""
        try:
            engine = HPLEngine()
            if not engine.load_file(file_path):
                return {
                    'success': False,
                    'error': f'无法加载文件: {file_path}'
                }

            if debug_mode:
                return engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
            else:
                return engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)

        except Exception as e:
            return {
                'success': False,
                'error': f"执行错误: {str(e)}",
                'error_type': type(e).__name__
            }

    def execute_code(self, code: str, timeout: float = 5.0,
                    call_target: Optional[str] = None, call_args: Optional[List] = None,
                    debug_mode: bool = False, file_path: Optional[str] = None,
                    input_data: Optional[Any] = None) -> Dict[str, Any]:
        temp_dir = tempfile.mkdtemp(prefix='hpl_sandbox_')
        temp_file = os.path.join(temp_dir, 'code.hpl')

        try:
            copied_files, _, not_found = copy_include_files(
                code, temp_dir, current_file=file_path
            )

            if not_found:
                logger.warning(f"未找到的 include 文件: {', '.join(not_found)}")

            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            result = self.execute(
                temp_file, timeout=timeout, call_target=call_target,
                call_args=call_args, debug_mode=debug_mode, input_data=input_data
            )

            return result

        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass


class HPLExecutionService:
    """
    HPL 执行服务
    统一入口，整合引擎、沙箱和调试功能
    """

    def __init__(self):
        self._runtime_available = check_runtime_available()
        self._default_sandbox = None

    def get_default_sandbox(self) -> SandboxExecutor:
        if self._default_sandbox is None:
            self._default_sandbox = SandboxExecutor()
        return self._default_sandbox

    def execute_file(self, file_path: str, debug_mode: bool = False,
                    call_target: Optional[str] = None, call_args: Optional[List] = None,
                    input_data: Optional[Any] = None, use_sandbox: bool = True) -> Dict[str, Any]:
        """
        执行 HPL 文件
        """
        if not self._runtime_available:
            return {
                'success': False,
                'error': 'hpl_runtime 不可用，无法执行代码',
                'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
            }

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {file_path}'}

        try:
            if use_sandbox:
                sandbox = self.get_default_sandbox()
                return sandbox.execute(
                    file_path, timeout=5.0, call_target=call_target,
                    call_args=call_args, debug_mode=debug_mode, input_data=input_data
                )
            else:
                engine = HPLEngine()
                if not engine.load_file(file_path):
                    return {'success': False, 'error': f'无法加载文件: {file_path}'}

                if debug_mode:
                    return engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
                else:
                    return engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)

        except Exception as e:
            return {
                'success': False,
                'error': f"执行错误: {str(e)}",
                'error_type': type(e).__name__
            }

    def execute_code(self, code: str, debug_mode: bool = False,
                    call_target: Optional[str] = None, call_args: Optional[List] = None,
                    file_path: Optional[str] = None, input_data: Optional[Any] = None,
                    use_sandbox: bool = True) -> Dict[str, Any]:
        """
        执行 HPL 代码字符串
        """
        if not self._runtime_available:
            return {
                'success': False,
                'error': 'hpl_runtime 不可用，无法执行代码',
                'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
            }

        try:
            if use_sandbox:
                sandbox = self.get_default_sandbox()
                return sandbox.execute_code(
                    code, timeout=5.0, call_target=call_target, call_args=call_args,
                    debug_mode=debug_mode, file_path=file_path, input_data=input_data
                )
            else:
                engine = HPLEngine()
                engine.load_code(code, file_path)

                if debug_mode:
                    return engine.debug(call_target=call_target, call_args=call_args, input_data=input_data)
                else:
                    return engine.execute(call_target=call_target, call_args=call_args, input_data=input_data)

        except Exception as e:
            return {
                'success': False,
                'error': f"执行错误: {str(e)}",
                'error_type': type(e).__name__
            }

    def validate_code(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """验证代码"""
        try:
            engine = HPLEngine()
            engine.load_code(code, file_path)
            return engine.validate()
        except ImportError:
            return [{
                'line': 1, 'column': 1, 'severity': 'error',
                'message': 'hpl_runtime 不可用'
            }]

    def get_completions(self, code: str, line: int, column: int,
                       prefix: str = "", file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取代码补全"""
        try:
            engine = HPLEngine()
            engine.load_code(code, file_path)
            return engine.get_completions(line, column, prefix)
        except ImportError:
            return []

    def get_code_outline(self, code: str, file_path: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """获取代码大纲"""
        try:
            engine = HPLEngine()
            engine.load_code(code, file_path)
            return engine.get_code_outline()
        except ImportError:
            return {'classes': [], 'functions': [], 'objects': [], 'imports': []}


# 全局服务实例
_execution_service = None

def get_execution_service() -> HPLExecutionService:
    """获取全局执行服务实例"""
    global _execution_service
    if _execution_service is None:
        _execution_service = HPLExecutionService()
    return _execution_service

# 便捷函数
def execute_hpl_file(file_path: str, **kwargs) -> Dict[str, Any]:
    service = get_execution_service()
    return service.execute_file(file_path, **kwargs)

def execute_hpl_code(code: str, **kwargs) -> Dict[str, Any]:
    service = get_execution_service()
    return service.execute_code(code, **kwargs)

def validate_hpl_code(code: str, **kwargs) -> List[Dict[str, Any]]:
    service = get_execution_service()
    return service.validate_code(code, **kwargs)

def get_hpl_completions(code: str, **kwargs) -> List[Dict[str, Any]]:
    service = get_execution_service()
    return service.get_completions(code, **kwargs)

def get_hpl_outline(code: str, **kwargs) -> Dict[str, List[Dict[str, Any]]]:
    service = get_execution_service()
    return service.get_code_outline(code, **kwargs)
