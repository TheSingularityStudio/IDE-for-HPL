"""
调试服务
提供高级调试功能，集成 hpl_runtime 的 DebugInterpreter
"""

import sys
import os
import logging
import tempfile
import time
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field

from config import PROJECT_ROOT, ALLOWED_EXAMPLES_DIR

logger = logging.getLogger(__name__)


@dataclass
class Breakpoint:
    """断点信息"""
    line: int
    condition: Optional[str] = None  # 条件表达式（可选）
    enabled: bool = True
    hit_count: int = 0


@dataclass
class VariableSnapshot:
    """变量快照"""
    line: int
    local_scope: Dict[str, Any] = field(default_factory=dict)
    global_scope: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionTraceEntry:
    """执行跟踪条目"""
    event_type: str  # FUNCTION_CALL, FUNCTION_RETURN, VARIABLE_ASSIGN, ERROR_CATCH
    line: Optional[int]
    details: Dict[str, Any]
    timestamp: float


@dataclass
class FunctionStats:
    """函数执行统计"""
    name: str
    calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0


class HPLDebugService:
    """HPL 调试服务"""
    
    def __init__(self):
        self.breakpoints: Dict[int, Breakpoint] = {}
        self.current_file: Optional[str] = None
        self.is_debugging: bool = False
        self.on_breakpoint_hit: Optional[Callable[[int, Dict], None]] = None
        self._trace_history: List[ExecutionTraceEntry] = []
        self._variable_history: List[VariableSnapshot] = []
        self._function_stats: Dict[str, FunctionStats] = {}
        self._current_function: Optional[str] = None
        self._function_start_time: Optional[float] = None
        
        # 检查 hpl_runtime 可用性
        self._runtime_available = self._check_runtime()
    
    def _check_runtime(self) -> bool:
        """检查 hpl_runtime 是否可用"""
        try:
            from hpl_runtime import DebugInterpreter
            return True
        except ImportError:
            logger.warning("hpl_runtime 不可用，调试功能将受限")
            return False
    
    def set_breakpoint(self, line: int, condition: Optional[str] = None) -> bool:
        """
        设置断点
        
        Args:
            line: 行号（1-based）
            condition: 可选的条件表达式
        
        Returns:
            bool: 是否成功设置
        """
        if line < 1:
            logger.error(f"无效的行号: {line}")
            return False
        
        self.breakpoints[line] = Breakpoint(line=line, condition=condition)
        logger.info(f"在 {line} 行设置断点" + (f" (条件: {condition})" if condition else ""))
        return True
    
    def clear_breakpoint(self, line: int) -> bool:
        """
        清除断点
        
        Args:
            line: 行号
        
        Returns:
            bool: 是否成功清除
        """
        if line in self.breakpoints:
            del self.breakpoints[line]
            logger.info(f"清除 {line} 行的断点")
            return True
        return False
    
    def clear_all_breakpoints(self):
        """清除所有断点"""
        self.breakpoints.clear()
        logger.info("清除所有断点")
    
    def toggle_breakpoint(self, line: int) -> bool:
        """
        切换断点状态
        
        Args:
            line: 行号
        
        Returns:
            bool: 切换后断点是否存在
        """
        if line in self.breakpoints:
            self.clear_breakpoint(line)
            return False
        else:
            self.set_breakpoint(line)
            return True
    
    def check_breakpoint(self, line: int, variables: Optional[Dict] = None) -> bool:
        """
        检查指定行是否命中断点
        
        Args:
            line: 当前行号
            variables: 当前变量环境（用于条件断点）
        
        Returns:
            bool: 是否命中断点
        """
        if line not in self.breakpoints:
            return False
        
        bp = self.breakpoints[line]
        if not bp.enabled:
            return False
        
        # 检查条件
        if bp.condition and variables:
            # 简单的条件评估（可以扩展）
            try:
                # 这里可以实现更复杂的条件评估
                pass
            except Exception as e:
                logger.error(f"评估断点条件失败: {e}")
                return False
        
        bp.hit_count += 1
        return True
    
    def debug_file(self, file_path: str, 
                   call_target: Optional[str] = None,
                   call_args: Optional[List] = None) -> Dict[str, Any]:
        """
        调试执行 HPL 文件
        
        Args:
            file_path: HPL 文件路径
            call_target: 可选的调用目标函数
            call_args: 可选的调用参数
        
        Returns:
            dict: 调试结果
        """
        if not self._runtime_available:
            return {
                'success': False,
                'error': 'hpl_runtime 不可用，无法使用调试功能',
                'debug_info': {}
            }
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'文件不存在: {file_path}',
                'debug_info': {}
            }
        
        self.current_file = file_path
        self._trace_history.clear()
        self._variable_history.clear()
        self._function_stats.clear()
        
        try:
            # 添加 examples 目录到 Python 模块搜索路径
            if ALLOWED_EXAMPLES_DIR not in sys.path:
                sys.path.insert(0, ALLOWED_EXAMPLES_DIR)
            
            from hpl_runtime import DebugInterpreter, HPLSyntaxError, HPLRuntimeError
            
            # 创建调试解释器
            interpreter = DebugInterpreter(debug_mode=True, verbose=True)
            
            # 执行
            start_time = time.time()
            result = interpreter.run(file_path, call_target=call_target, call_args=call_args)
            total_time = time.time() - start_time
            
            # 处理调试信息
            debug_info = result.get('debug_info', {})
            
            # 转换执行跟踪
            execution_trace = debug_info.get('execution_trace', [])
            self._trace_history = [
                ExecutionTraceEntry(
                    event_type=entry.get('type', 'UNKNOWN'),
                    line=entry.get('line'),
                    details=entry.get('details', {}),
                    timestamp=entry.get('timestamp', 0)
                )
                for entry in execution_trace
            ]
            
            # 转换变量快照
            variable_snapshots = debug_info.get('variable_snapshots', [])
            self._variable_history = [
                VariableSnapshot(
                    line=snapshot.get('line', 0),
                    local_scope=snapshot.get('local_scope', {}),
                    global_scope=snapshot.get('global_scope', {}),
                    timestamp=snapshot.get('timestamp', 0)
                )
                for snapshot in variable_snapshots
            ]
            
            # 分析函数统计
            self._analyze_function_stats(execution_trace)
            
            # 检查断点命中
            breakpoint_hits = []
            for entry in self._trace_history:
                if entry.line and entry.line in self.breakpoints:
                    if self.check_breakpoint(entry.line):
                        breakpoint_hits.append({
                            'line': entry.line,
                            'event': entry.event_type,
                            'details': entry.details
                        })
                        # 触发回调
                        if self.on_breakpoint_hit:
                            self.on_breakpoint_hit(entry.line, entry.details)
            
            return {
                'success': result.get('success', False),
                'error': str(result.get('error')) if result.get('error') else None,
                'execution_time': total_time,
                'debug_info': {
                    'execution_trace': [self._entry_to_dict(e) for e in self._trace_history],
                    'variable_snapshots': [self._snapshot_to_dict(s) for s in self._variable_history],
                    'breakpoint_hits': breakpoint_hits,
                    'function_stats': {name: self._stats_to_dict(s) 
                                      for name, s in self._function_stats.items()},
                    'total_steps': len(self._trace_history),
                    'report': debug_info.get('report', '')
                }
            }
            
        except HPLSyntaxError as e:
            return {
                'success': False,
                'error': f"语法错误 (行 {e.line}, 列 {e.column}): {e.message}",
                'line': e.line,
                'column': e.column,
                'error_key': getattr(e, 'error_key', None),
                'debug_info': {}
            }
        except HPLRuntimeError as e:
            return {
                'success': False,
                'error': f"运行时错误: {e.message}",
                'line': getattr(e, 'line', None),
                'column': getattr(e, 'column', None),
                'call_stack': getattr(e, 'call_stack', []),
                'error_key': getattr(e, 'error_key', None),
                'debug_info': {
                    'execution_trace': [self._entry_to_dict(e) for e in self._trace_history],
                    'variable_snapshots': [self._snapshot_to_dict(s) for s in self._variable_history]
                }
            }
        except Exception as e:
            logger.error(f"调试执行失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"调试执行失败: {str(e)}",
                'debug_info': {}
            }
    
    def _analyze_function_stats(self, execution_trace: List[Dict]):
        """分析函数执行统计"""
        current_function = None
        function_start_time = None
        
        for entry in execution_trace:
            event_type = entry.get('type')
            timestamp = entry.get('timestamp', 0)
            details = entry.get('details', {})
            
            if event_type == 'FUNCTION_CALL':
                current_function = details.get('name')
                function_start_time = timestamp
                
                if current_function not in self._function_stats:
                    self._function_stats[current_function] = FunctionStats(name=current_function)
                
                self._function_stats[current_function].calls += 1
                
            elif event_type == 'FUNCTION_RETURN' and current_function:
                duration = timestamp - function_start_time if function_start_time else 0
                stats = self._function_stats[current_function]
                stats.total_time += duration
                stats.min_time = min(stats.min_time, duration)
                stats.max_time = max(stats.max_time, duration)
                
                current_function = None
                function_start_time = None
    
    def get_variable_at_line(self, line: int) -> Optional[VariableSnapshot]:
        """
        获取指定行的变量状态
        
        Args:
            line: 行号
        
        Returns:
            VariableSnapshot: 变量快照，如果没有则返回 None
        """
        for snapshot in reversed(self._variable_history):
            if snapshot.line <= line:
                return snapshot
        return None
    
    def get_execution_trace(self) -> List[ExecutionTraceEntry]:
        """获取执行跟踪历史"""
        return self._trace_history.copy()
    
    def get_function_stats(self) -> Dict[str, FunctionStats]:
        """获取函数执行统计"""
        return self._function_stats.copy()
    
    def get_coverage_info(self, source_code: str) -> Dict[str, Any]:
        """
        获取代码覆盖率信息
        
        Args:
            source_code: 源代码字符串
        
        Returns:
            dict: 覆盖率信息
        """
        executed_lines = set()
        for entry in self._trace_history:
            if entry.line:
                executed_lines.add(entry.line)
        
        total_lines = len(source_code.split('\n'))
        
        return {
            'executed_lines': sorted(executed_lines),
            'total_lines': total_lines,
            'coverage_percent': (len(executed_lines) / total_lines * 100) if total_lines > 0 else 0,
            'uncovered_lines': sorted(set(range(1, total_lines + 1)) - executed_lines)
        }
    
    def step_back(self, steps: int = 1) -> Optional[ExecutionTraceEntry]:
        """
        回退执行步骤（用于反向调试）
        
        Args:
            steps: 回退步数
        
        Returns:
            ExecutionTraceEntry: 回退到的执行条目
        """
        if not self._trace_history:
            return None
        
        index = max(0, len(self._trace_history) - steps - 1)
        return self._trace_history[index]
    
    def _entry_to_dict(self, entry: ExecutionTraceEntry) -> Dict[str, Any]:
        """转换执行条目为字典"""
        return {
            'type': entry.event_type,
            'line': entry.line,
            'details': entry.details,
            'timestamp': entry.timestamp
        }
    
    def _snapshot_to_dict(self, snapshot: VariableSnapshot) -> Dict[str, Any]:
        """转换变量快照为字典"""
        return {
            'line': snapshot.line,
            'local_scope': snapshot.local_scope,
            'global_scope': snapshot.global_scope,
            'timestamp': snapshot.timestamp
        }
    
    def _stats_to_dict(self, stats: FunctionStats) -> Dict[str, Any]:
        """转换函数统计为字典"""
        return {
            'name': stats.name,
            'calls': stats.calls,
            'total_time': stats.total_time,
            'avg_time': stats.total_time / stats.calls if stats.calls > 0 else 0,
            'min_time': stats.min_time if stats.min_time != float('inf') else 0,
            'max_time': stats.max_time
        }


class ErrorAnalyzer:
    """错误分析器，提供错误上下文和修复建议"""
    
    def __init__(self):
        self._runtime_available = self._check_runtime()
    
    def _check_runtime(self) -> bool:
        """检查 hpl_runtime 是否可用"""
        try:
            from hpl_runtime.debug import ErrorAnalyzer as RuntimeErrorAnalyzer
            return True
        except ImportError:
            logger.warning("hpl_runtime.debug.ErrorAnalyzer 不可用")
            return False
    
    def analyze_error(self, error: Exception, source_code: str) -> Dict[str, Any]:
        """
        分析错误并提供上下文
        
        Args:
            error: 异常对象
            source_code: 源代码
        
        Returns:
            dict: 错误分析结果
        """
        result = {
            'error_type': type(error).__name__,
            'message': str(error),
            'error_line': None,
            'surrounding_lines': [],
            'suggestions': [],
            'severity': 'error'
        }
        
        # 提取行号
        line_num = None
        if hasattr(error, 'line'):
            line_num = error.line
        elif hasattr(error, 'lineno'):
            line_num = error.lineno
        
        if line_num:
            result['error_line'] = line_num
            result['surrounding_lines'] = self._get_surrounding_lines(source_code, line_num)
        
        # 尝试使用 hpl_runtime 的 ErrorAnalyzer
        if self._runtime_available:
            try:
                from hpl_runtime.debug import ErrorAnalyzer as RuntimeErrorAnalyzer
                from hpl_runtime.debug import ErrorContext
                
                analyzer = RuntimeErrorAnalyzer()
                context = analyzer.analyze_error(error, source_code=source_code)
                
                if hasattr(context, 'suggestions'):
                    result['suggestions'] = context.suggestions
                if hasattr(context, 'severity'):
                    result['severity'] = context.severity
                    
            except Exception as e:
                logger.error(f"使用 hpl_runtime ErrorAnalyzer 失败: {e}")
        
        # 生成基本建议
        if not result['suggestions']:
            result['suggestions'] = self._generate_basic_suggestions(error, line_num)
        
        return result
    
    def _get_surrounding_lines(self, source_code: str, error_line: int, 
                                  context_lines: int = 3) -> List[Dict[str, Any]]:
        """
        获取错误行周围的代码
        
        Args:
            source_code: 源代码
            error_line: 错误行号（1-based）
            context_lines: 上下文行数
        
        Returns:
            list: 周围行信息
        """
        lines = source_code.split('\n')
        start = max(0, error_line - context_lines - 1)
        end = min(len(lines), error_line + context_lines)
        
        surrounding = []
        for i in range(start, end):
            surrounding.append({
                'line_number': i + 1,
                'content': lines[i],
                'is_error_line': (i + 1) == error_line
            })
        
        return surrounding
    
    def _generate_basic_suggestions(self, error: Exception, line_num: Optional[int]) -> List[str]:
        """生成基本修复建议"""
        suggestions = []
        error_msg = str(error).lower()
        
        if 'syntax' in error_msg or 'parse' in error_msg:
            suggestions.append("检查语法错误，确保所有括号、引号都正确匹配")
            suggestions.append("检查缩进是否正确（HPL 使用 YAML 格式）")
        
        if 'undefined' in error_msg or 'name' in error_msg:
            suggestions.append("检查变量或函数名是否拼写正确")
            suggestions.append("确保在使用前已经定义了该变量或函数")
        
        if 'indent' in error_msg:
            suggestions.append("检查缩进是否一致，建议使用空格而非 Tab")
        
        if 'import' in error_msg:
            suggestions.append("检查模块名称是否正确")
            suggestions.append("确保模块文件存在于搜索路径中")
        
        if not suggestions:
            suggestions.append("检查代码逻辑是否正确")
            suggestions.append("参考 HPL 语法手册了解正确的语法")
        
        return suggestions


# 全局服务实例
_debug_service = None
_error_analyzer = None


def get_debug_service() -> HPLDebugService:
    """获取全局调试服务实例"""
    global _debug_service
    if _debug_service is None:
        _debug_service = HPLDebugService()
    return _debug_service


def get_error_analyzer() -> ErrorAnalyzer:
    """获取全局错误分析器实例"""
    global _error_analyzer
    if _error_analyzer is None:
        _error_analyzer = ErrorAnalyzer()
    return _error_analyzer


def debug_file(file_path: str, 
               call_target: Optional[str] = None,
               call_args: Optional[List] = None) -> Dict[str, Any]:
    """
    便捷函数：调试执行 HPL 文件
    
    Args:
        file_path: HPL 文件路径
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
    
    Returns:
        dict: 调试结果
    """
    service = get_debug_service()
    return service.debug_file(file_path, call_target, call_args)


def analyze_error(error: Exception, source_code: str) -> Dict[str, Any]:
    """
    便捷函数：分析错误
    
    Args:
        error: 异常对象
        source_code: 源代码
    
    Returns:
        dict: 错误分析结果
    """
    analyzer = get_error_analyzer()
    return analyzer.analyze_error(error, source_code)
