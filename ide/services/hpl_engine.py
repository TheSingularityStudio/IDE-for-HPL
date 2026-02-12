"""
HPL 核心引擎
提供统一的 HPL 解析、验证、执行和调试功能
基于 hpl_runtime 的标准集成模式
"""

import os
import sys
import tempfile
import logging
import hashlib
import pickle
import io
import contextlib
import queue
import threading
from typing import Dict, List, Any, Optional, Tuple, Generator
from dataclasses import dataclass

# 导入统一的运行时管理器（P0修复）
from ide.services.runtime_manager import check_runtime_available, get_runtime_manager

# P2修复：导入include文件处理
from ide.services.code_processor import copy_include_files

# 配置日志
logger = logging.getLogger(__name__)



@dataclass
class Diagnostic:
    """诊断信息"""
    line: int
    column: int
    severity: str  # 'error', 'warning', 'info'
    message: str
    code: Optional[str] = None
    error_key: Optional[str] = None


class ParseCache:
    """解析结果缓存"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '.cache')
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, code: str) -> str:
        """根据代码内容生成缓存键"""
        return hashlib.md5(code.encode('utf-8')).hexdigest()
    
    def get(self, code: str) -> Optional[Tuple]:
        """获取缓存的解析结果"""
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
        """缓存解析结果"""
        cache_key = self._get_cache_key(code)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pickle")
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(parse_result, f)
        except Exception as e:
            logger.debug(f"写入缓存失败: {e}")


class HPLEngine:
    """
    HPL IDE 引擎
    统一封装 hpl_runtime 的功能，提供验证、补全、执行接口
    """
    
    def __init__(self, use_cache: bool = True):
        self.current_file: Optional[str] = None
        self.source_code: Optional[str] = None
        self._parser = None
        self._parse_result: Optional[Tuple] = None
        self._cache = ParseCache() if use_cache else None
        
        # P0修复：使用统一的运行时检查
        self._runtime_available = check_runtime_available()
        if not self._runtime_available:
            raise ImportError("hpl_runtime 不可用，无法创建 HPLEngine")
    
    def load_file(self, file_path: str) -> bool:
        """
        加载 HPL 文件
        
        Args:
            file_path: HPL 文件路径
            
        Returns:
            bool: 是否成功加载
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.source_code = f.read()
            self.current_file = file_path
            self._parse_result = None  # 重置解析结果
            return True
        except Exception as e:
            logger.error(f"加载文件失败: {e}")
            return False
    
    def load_code(self, code: str, file_path: Optional[str] = None):
        """
        直接从代码字符串加载
        
        Args:
            code: HPL 代码字符串
            file_path: 可选的文件路径（用于错误显示）
        """
        self.source_code = code
        self.current_file = file_path or "<memory>"
        self._parse_result = None
    
    def _parse(self) -> Optional[Tuple]:
        """
        解析代码，返回解析结果
        
        Returns:
            Tuple: (classes, objects, functions, main_func, call_target, call_args, imports)
        """
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
        from hpl_runtime import HPLParser
        
        # P2修复：创建临时目录并复制include文件
        temp_dir = tempfile.mkdtemp(prefix='hpl_parse_')
        temp_file = os.path.join(temp_dir, 'temp_code.hpl')
        
        try:
            # 复制include文件到临时目录
            copied_files, _, not_found = copy_include_files(
                self.source_code, temp_dir, current_file=self.current_file
            )
            if not_found:
                logger.warning(f"解析时未找到的include文件: {', '.join(not_found)}")
            
            # 写入代码到临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(self.source_code)
            
            parser = HPLParser(temp_file)
            result = parser.parse()
            self._parse_result = result
            
            # 缓存结果
            if self._cache:
                self._cache.set(self.source_code, result)
            
            return result
            
        finally:
            # 清理临时目录
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

    
    def validate(self) -> List[Diagnostic]:
        """
        验证代码，返回诊断信息列表
        
        Returns:
            List[Diagnostic]: 诊断信息列表
        """
        diagnostics = []
        
        if not self.source_code:
            diagnostics.append(Diagnostic(
                line=1, column=1, severity='error',
                message="代码为空", code=None
            ))
            return diagnostics
        
        try:
            from hpl_runtime import HPLSyntaxError, HPLImportError, format_error_for_user
            
            self._parse()
            
        except HPLSyntaxError as e:
            # 使用 format_error_for_user 获取友好错误消息
            user_message = format_error_for_user(e, self.source_code)
            
            diagnostics.append(Diagnostic(
                line=e.line or 1,
                column=e.column or 1,
                severity='error',
                message=user_message,
                code=self._get_code_at_line(e.line) if e.line else None,
                error_key=getattr(e, 'error_key', None)
            ))
            
        except HPLImportError as e:
            # 导入错误作为警告（在验证阶段不需要实际文件存在）
            diagnostics.append(Diagnostic(
                line=getattr(e, 'line', 1),
                column=getattr(e, 'column', 1),
                severity='warning',
                message=f"导入警告: {str(e)}",
                code=None
            ))
            
        except Exception as e:
            diagnostics.append(Diagnostic(
                line=1, column=1, severity='error',
                message=f"验证错误: {str(e)}", code=None
            ))
        
        return diagnostics
    
    def get_completions(self, line: int, column: int, prefix: str = "") -> List[Dict[str, Any]]:
        """
        获取代码补全项
        
        Args:
            line: 当前行号（1-based）
            column: 当前列号（1-based）
            prefix: 当前输入前缀
            
        Returns:
            List[Dict]: 补全项列表
        """
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
                    'documentation': f"类 {class_name}" + 
                                    (f"\n方法: {', '.join(methods)}" if methods else ""),
                    'insertText': class_name
                })
        
        # 对象补全
        for obj_name, obj in objects.items():
            if obj_name.startswith(prefix):
                class_name = "Unknown"
                if hasattr(obj, 'hpl_class') and hasattr(obj.hpl_class, 'name'):
                    class_name = obj.hpl_class.name
                
                items.append({
                    'label': obj_name,
                    'kind': 'Object',
                    'detail': f"Object: {obj_name} ({class_name})",
                    'documentation': f"对象 {obj_name}，类型: {class_name}",
                    'insertText': obj_name
                })
        
        # 函数补全
        for func_name, func in functions.items():
            if func_name.startswith(prefix):
                params = getattr(func, 'params', [])
                
                # 生成带占位符的插入文本
                param_snippets = [f"${{{i+1}:{param}}}" for i, param in enumerate(params)]
                insert_text = f"{func_name}({', '.join(param_snippets)})"

                
                items.append({
                    'label': func_name,
                    'kind': 'Function',
                    'detail': f"Function: {func_name}({', '.join(params)})",
                    'documentation': f"函数 {func_name}" + 
                                    (f"\n参数: {', '.join(params)}" if params else ""),
                    'insertText': insert_text,
                    'params': params
                })
        
        # 添加 main 函数
        if main_func and 'main'.startswith(prefix):
            params = getattr(main_func, 'params', [])
            param_snippets = [f"${{{i+1}:{param}}}" for i, param in enumerate(params)]
            insert_text = f"main({', '.join(param_snippets)})"

            
            items.insert(0, {
                'label': 'main',
                'kind': 'Function',
                'detail': f"Function: main({', '.join(params)})",
                'documentation': "主函数" + 
                                (f"\n参数: {', '.join(params)}" if params else ""),
                'insertText': insert_text,
                'params': params,
                'is_main': True
            })
        
        # 按标签排序
        items.sort(key=lambda x: x['label'])
        
        return items
    
    def execute(self, call_target: Optional[str] = None,
                call_args: Optional[List] = None,
                input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        执行代码
        
        Args:
            call_target: 可选的调用目标函数
            call_args: 可选的调用参数
            input_data: 可选的输入数据（用于input()函数）
            
        Returns:
            Dict: 执行结果
        """
        parse_result = self._parse()
        if not parse_result:
            return {
                'success': False,
                'error': '解析失败，无法执行'
            }
        
        classes, objects, functions, main_func, _, _, _ = parse_result
        
        # 检查是否有可执行的函数
        if not main_func and not call_target:
            return {
                'success': False,
                'error': '没有 main 函数或 call 目标'
            }
        
        # P1修复：准备输入数据
        stdin_buffer = None
        original_stdin = None
        if input_data is not None:
            if isinstance(input_data, list):
                input_data = '\n'.join(str(item) for item in input_data)
            stdin_buffer = io.StringIO(str(input_data))
            original_stdin = sys.stdin
        
        try:
            from hpl_runtime import HPLEvaluator, HPLRuntimeError, format_error_for_user
            
            # 捕获输出
            output_buffer = io.StringIO()
            
            # P1修复：重定向stdin和stdout
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
            # 使用 format_error_for_user 获取友好错误消息
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
            # P1修复：恢复原始stdin
            if original_stdin is not None:
                sys.stdin = original_stdin
    
    def execute_streaming(self, call_target: Optional[str] = None,
                         call_args: Optional[List] = None,
                         input_data: Optional[Any] = None) -> Generator[Dict[str, Any], None, None]:
        """
        P1修复：流式执行代码，实时产生输出
        
        Args:
            call_target: 可选的调用目标函数
            call_args: 可选的调用参数
            input_data: 可选的输入数据（用于input()函数）
            
        Yields:
            Dict: 输出块 {'type': 'stdout'|'stderr'|'error'|'done', 'data': str}
        """
        parse_result = self._parse()
        if not parse_result:
            yield {'type': 'error', 'data': '解析失败，无法执行'}
            return
        
        classes, objects, functions, main_func, _, _, _ = parse_result
        
        # 检查是否有可执行的函数
        if not main_func and not call_target:
            yield {'type': 'error', 'data': '没有 main 函数或 call 目标'}
            return
        
        # 准备输入数据
        stdin_buffer = None
        original_stdin = None
        if input_data is not None:
            if isinstance(input_data, list):
                input_data = '\n'.join(str(item) for item in input_data)
            stdin_buffer = io.StringIO(str(input_data))
            original_stdin = sys.stdin
            sys.stdin = stdin_buffer
        
        # 创建输出队列
        output_queue = queue.Queue()
        
        class StreamingBuffer:
            """流式输出缓冲区"""
            def write(self, data):
                if data:
                    output_queue.put({'type': 'stdout', 'data': str(data)})
            
            def flush(self):
                pass
        
        def execute_in_thread():
            """在后台线程中执行代码"""
            try:
                from hpl_runtime import HPLEvaluator, HPLRuntimeError, format_error_for_user
                
                stream_buffer = StreamingBuffer()
                
                with contextlib.redirect_stdout(stream_buffer):
                    evaluator = HPLEvaluator(
                        classes=classes,
                        objects=objects,
                        functions=functions,
                        main_func=main_func,
                        call_target=call_target,
                        call_args=call_args or []
                    )
                    evaluator.run()
                
                output_queue.put({'type': 'done', 'data': None})
                
            except HPLRuntimeError as e:
                user_message = format_error_for_user(e, self.source_code)
                output_queue.put({
                    'type': 'error',
                    'data': user_message,
                    'error_type': type(e).__name__,
                    'line': getattr(e, 'line', None),
                    'column': getattr(e, 'column', None),
                    'call_stack': getattr(e, 'call_stack', []),
                    'error_key': getattr(e, 'error_key', None)
                })
            except Exception as e:
                output_queue.put({
                    'type': 'error',
                    'data': str(e),
                    'error_type': type(e).__name__
                })
            finally:
                # 恢复原始stdin
                if original_stdin is not None:
                    sys.stdin = original_stdin
        
        # 启动执行线程
        thread = threading.Thread(target=execute_in_thread)
        thread.start()
        
        # 生成输出块
        while True:
            try:
                msg = output_queue.get(timeout=0.1)
                if msg['type'] == 'done':
                    break
                yield msg
            except queue.Empty:
                if not thread.is_alive():
                    # 线程已结束但没有收到done消息
                    break
                # 发送心跳保持连接
                yield {'type': 'heartbeat', 'data': ''}
        
        # 等待线程结束
        thread.join(timeout=1.0)
    
    def debug(self, call_target: Optional[str] = None,
              call_args: Optional[List] = None,
              input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        调试执行代码
        
        Args:
            call_target: 可选的调用目标函数
            call_args: 可选的调用参数
            input_data: 可选的输入数据（用于input()函数）
            
        Returns:
            Dict: 调试结果
        """
        # P0修复：修复临时文件变量作用域问题
        temp_file = None
        temp_dir = None
        file_to_debug = None
        
        try:
            if not self.current_file or self.current_file == "<memory>":
                # 调试模式需要文件路径，创建临时目录和文件
                temp_dir = tempfile.mkdtemp(prefix='hpl_debug_')
                temp_file = os.path.join(temp_dir, 'debug_temp.hpl')
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(self.source_code or "")
                
                file_to_debug = temp_file
                logger.info(f"创建调试临时文件: {temp_file}")
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
            # P0修复：统一清理临时文件和目录
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    logger.debug(f"清理临时文件: {temp_file}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {temp_file}, 错误: {e}")
            
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.debug(f"清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {temp_dir}, 错误: {e}")
    
    def _debug_file(self, file_path: str, call_target: Optional[str] = None,
                    call_args: Optional[List] = None,
                    input_data: Optional[Any] = None) -> Dict[str, Any]:
        """调试执行文件"""
        # P1修复：准备输入数据
        stdin_buffer = None
        original_stdin = None
        if input_data is not None:
            if isinstance(input_data, list):
                input_data = '\n'.join(str(item) for item in input_data)
            stdin_buffer = io.StringIO(str(input_data))
            original_stdin = sys.stdin
        
        try:
            from hpl_runtime import DebugInterpreter, HPLSyntaxError, HPLRuntimeError
            
            # P1修复：重定向stdin
            if stdin_buffer:
                sys.stdin = stdin_buffer
            
            interpreter = DebugInterpreter(debug_mode=True, verbose=True)
            result = interpreter.run(file_path, call_target=call_target, call_args=call_args)
            
            debug_info = result.get('debug_info', {})
            
            # 格式化调试结果
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
            
            # 添加变量监控信息
            snapshots = debug_info.get('variable_snapshots', [])
            if snapshots:
                formatted_result['final_variables'] = snapshots[-1]
            
            # 计算函数统计
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
            # P1修复：恢复原始stdin
            if original_stdin is not None:
                sys.stdin = original_stdin
    
    def _calculate_function_stats(self, execution_trace: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """计算函数执行统计"""
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
        
        # 计算平均值
        for func_name, func_stats in stats.items():
            if func_stats['calls'] > 0:
                func_stats['avg_time'] = func_stats['total_time'] / func_stats['calls']
            if func_stats['min_time'] == float('inf'):
                func_stats['min_time'] = 0
        
        return stats
    
    def get_code_outline(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取代码大纲
        
        Returns:
            Dict: 代码结构大纲
        """
        outline = {
            'classes': [],
            'functions': [],
            'objects': [],
            'imports': []
        }
        
        parse_result = self._parse()
        if not parse_result:
            return outline
        
        classes, objects, functions, main_func, _, _, imports = parse_result
        
        # 提取类信息
        for class_name, hpl_class in classes.items():
            methods = []
            if hasattr(hpl_class, 'methods'):
                for method_name, method in hpl_class.methods.items():
                    params = getattr(method, 'params', [])
                    methods.append({
                        'name': method_name,
                        'params': params
                    })
            
            parent = None
            if hasattr(hpl_class, 'parent') and hpl_class.parent:
                parent = hpl_class.parent.name if hasattr(hpl_class.parent, 'name') else str(hpl_class.parent)
            
            outline['classes'].append({
                'name': class_name,
                'parent': parent,
                'methods': methods
            })
        
        # 提取函数信息
        for func_name, func in functions.items():
            params = getattr(func, 'params', [])
            outline['functions'].append({
                'name': func_name,
                'params': params
            })
        
        # 提取 main 函数
        if main_func:
            params = getattr(main_func, 'params', [])
            outline['functions'].insert(0, {
                'name': 'main',
                'params': params,
                'is_main': True
            })
        
        # 提取对象信息
        for obj_name, obj in objects.items():
            class_name = "Unknown"
            if hasattr(obj, 'hpl_class') and hasattr(obj.hpl_class, 'name'):
                class_name = obj.hpl_class.name
            
            outline['objects'].append({
                'name': obj_name,
                'class': class_name
            })
        
        # 提取导入信息
        for imp in imports:
            module = imp.get('module', '')
            alias = imp.get('alias', module)
            outline['imports'].append({
                'module': module,
                'alias': alias
            })
        
        return outline
    
    def get_coverage_info(self) -> Dict[str, Any]:
        """
        获取代码覆盖率信息（需要先有调试执行结果）
        
        Returns:
            Dict: 覆盖率信息
        """
        # 这个方法需要在调试执行后调用
        # 实际覆盖率计算在 debug() 方法中通过 execution_trace 实现
        return {
            'executed_lines': [],
            'total_lines': len(self.source_code.split('\n')) if self.source_code else 0,
            'coverage_percent': 0,
            'uncovered_lines': []
        }
    
    def _get_code_at_line(self, line_num: Optional[int]) -> Optional[str]:
        """获取指定行的代码"""
        if not line_num or line_num < 1 or not self.source_code:
            return None
        
        lines = self.source_code.split('\n')
        if line_num <= len(lines):
            return lines[line_num - 1]
        return None


# 便捷函数
def validate_code(code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    验证代码的便捷函数
    
    Args:
        code: HPL 代码
        file_path: 可选的文件路径
        
    Returns:
        List[Dict]: 诊断信息列表
    """
    try:
        engine = HPLEngine()
        engine.load_code(code, file_path)
        diagnostics = engine.validate()
        return [vars(d) for d in diagnostics]
    except ImportError:
        return [{
            'line': 1, 'column': 1, 'severity': 'error',
            'message': 'hpl_runtime 不可用'
        }]


def get_completions(code: str, line: int, column: int, 
                  prefix: str = "", file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取代码补全的便捷函数
    
    Args:
        code: HPL 代码
        line: 行号
        column: 列号
        prefix: 前缀
        file_path: 可选的文件路径
        
    Returns:
        List[Dict]: 补全项列表
    """
    try:
        engine = HPLEngine()
        engine.load_code(code, file_path)
        return engine.get_completions(line, column, prefix)
    except ImportError:
        return []


def execute_code(code: str, call_target: Optional[str] = None,
                call_args: Optional[List] = None,
                file_path: Optional[str] = None,
                input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    执行代码的便捷函数
    
    Args:
        code: HPL 代码
        call_target: 调用目标
        call_args: 调用参数
        file_path: 可选的文件路径
        input_data: 可选的输入数据（用于input()函数）
        
    Returns:
        Dict: 执行结果
    """
    try:
        engine = HPLEngine()
        engine.load_code(code, file_path)
        return engine.execute(call_target, call_args, input_data)
    except ImportError as e:
        return {
            'success': False,
            'error': f'hpl_runtime 不可用: {str(e)}'
        }


def debug_code(code: str, call_target: Optional[str] = None,
              call_args: Optional[List] = None,
              file_path: Optional[str] = None,
              input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    调试代码的便捷函数
    
    Args:
        code: HPL 代码
        call_target: 调用目标
        call_args: 调用参数
        file_path: 可选的文件路径
        input_data: 可选的输入数据（用于input()函数）
        
    Returns:
        Dict: 调试结果
    """
    try:
        engine = HPLEngine()
        engine.load_code(code, file_path)
        return engine.debug(call_target, call_args, input_data)
    except ImportError as e:
        return {
            'success': False,
            'error': f'hpl_runtime 不可用: {str(e)}',
            'debug_info': {}
        }


def get_code_outline(code: str, file_path: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    获取代码大纲的便捷函数
    
    Args:
        code: HPL 代码
        file_path: 可选的文件路径
        
    Returns:
        Dict: 代码大纲
    """
    try:
        engine = HPLEngine()
        engine.load_code(code, file_path)
        return engine.get_code_outline()
    except ImportError:
        return {
            'classes': [],
            'functions': [],
            'objects': [],
            'imports': []
        }


def execute_code_streaming(code: str, call_target: Optional[str] = None,
                          call_args: Optional[List] = None,
                          file_path: Optional[str] = None,
                          input_data: Optional[Any] = None) -> Generator[Dict[str, Any], None, None]:
    """
    P1修复：流式执行代码的便捷函数
    
    Args:
        code: HPL 代码
        call_target: 调用目标
        call_args: 调用参数
        file_path: 可选的文件路径
        input_data: 可选的输入数据（用于input()函数）
        
    Yields:
        Dict: 输出块 {'type': 'stdout'|'stderr'|'error'|'done', 'data': str}
    """
    try:
        engine = HPLEngine()
        engine.load_code(code, file_path)
        yield from engine.execute_streaming(call_target, call_args, input_data)
    except ImportError as e:
        yield {
            'type': 'error',
            'data': f'hpl_runtime 不可用: {str(e)}'
        }
