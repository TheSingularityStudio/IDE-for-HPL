"""
调试服务
提供高级调试功能，集成 hpl_runtime 的 DebugInterpreter
基于 HPLEngine 实现统一的调试接口
"""

import os
import sys
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

# 导入核心引擎
try:
    from ide.services.hpl_engine import HPLEngine, check_runtime_available
    _engine_available = True
except ImportError:
    _engine_available = False

logger = logging.getLogger(__name__)


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


class HPLDebugService:
    """
    HPL 调试服务
    基于 HPLEngine 提供调试功能
    """
    
    def __init__(self):
        self.breakpoints: Dict[int, Breakpoint] = {}
        self.current_file: Optional[str] = None
        self.is_debugging: bool = False
        self.on_breakpoint_hit: Optional[Callable[[int, Dict], None]] = None
        
        # 检查运行时可用性
        self._runtime_available = check_runtime_available() if _engine_available else False
        if not self._runtime_available:
            logger.warning("hpl_runtime 不可用，调试功能将受限")
    
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
            try:
                # 简单的条件评估（可以扩展）
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
        self.is_debugging = True
        
        try:
            # 使用 HPLEngine 进行调试
            engine = HPLEngine()
            engine.load_file(file_path)
            
            result = engine.debug(call_target=call_target, call_args=call_args)
            
            # 检查断点命中
            self._check_breakpoints_in_trace(result)
            
            # 计算覆盖率
            if result.get('success'):
                result['coverage'] = self._calculate_coverage(
                    engine.source_code,
                    result.get('debug_info', {}).get('execution_trace', [])
                )
            
            return result
            
        except Exception as e:
            logger.error(f"调试执行失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"调试执行失败: {str(e)}",
                'debug_info': {}
            }
        finally:
            self.is_debugging = False
    
    def debug_code(self, code: str, file_path: Optional[str] = None,
                   call_target: Optional[str] = None,
                   call_args: Optional[List] = None) -> Dict[str, Any]:
        """
        调试执行 HPL 代码
        
        Args:
            code: HPL 源代码
            file_path: 可选的文件路径
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
        
        self.current_file = file_path or "<memory>"
        self.is_debugging = True
        
        try:
            # 使用 HPLEngine 进行调试
            engine = HPLEngine()
            engine.load_code(code, file_path)
            
            result = engine.debug(call_target=call_target, call_args=call_args)
            
            # 检查断点命中
            self._check_breakpoints_in_trace(result)
            
            # 计算覆盖率
            if result.get('success'):
                result['coverage'] = self._calculate_coverage(
                    code,
                    result.get('debug_info', {}).get('execution_trace', [])
                )
            
            return result
            
        except Exception as e:
            logger.error(f"调试执行失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"调试执行失败: {str(e)}",
                'debug_info': {}
            }
        finally:
            self.is_debugging = False
    
    def _check_breakpoints_in_trace(self, result: Dict[str, Any]):
        """检查执行跟踪中的断点命中"""
        trace = result.get('debug_info', {}).get('execution_trace', [])
        breakpoint_hits = []
        
        for entry in trace:
            line = entry.get('line')
            if line and line in self.breakpoints:
                if self.check_breakpoint(line, entry.get('details', {})):
                    breakpoint_hits.append({
                        'line': line,
                        'event': entry.get('type'),
                        'details': entry.get('details', {})
                    })
                    # 触发回调
                    if self.on_breakpoint_hit:
                        self.on_breakpoint_hit(line, entry.get('details', {}))
        
        result['breakpoint_hits'] = breakpoint_hits
    
    def _calculate_coverage(self, source_code: str, 
                           execution_trace: List[Dict]) -> Dict[str, Any]:
        """计算代码覆盖率"""
        if not source_code:
            return {
                'executed_lines': [],
                'total_lines': 0,
                'coverage_percent': 0,
                'uncovered_lines': []
            }
        
        executed_lines = set()
        for entry in execution_trace:
            line = entry.get('line')
            if line:
                executed_lines.add(line)
        
        total_lines = len(source_code.split('\n'))
        all_lines = set(range(1, total_lines + 1))
        
        return {
            'executed_lines': sorted(executed_lines),
            'total_lines': total_lines,
            'coverage_percent': (len(executed_lines) / total_lines * 100) if total_lines > 0 else 0,
            'uncovered_lines': sorted(all_lines - executed_lines)
        }
    
    def get_variable_at_line(self, line: int, 
                            result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        获取指定行的变量状态
        
        Args:
            line: 行号
            result: 调试结果
        
        Returns:
            dict: 变量快照，如果没有则返回 None
        """
        snapshots = result.get('debug_info', {}).get('variable_snapshots', [])
        
        for snapshot in reversed(snapshots):
            if snapshot.get('line', 0) <= line:
                return snapshot
        
        return None
    
    def step_back(self, result: Dict[str, Any], steps: int = 1) -> Optional[Dict[str, Any]]:
        """
        回退执行步骤（用于反向调试）
        
        Args:
            result: 调试结果
            steps: 回退步数
        
        Returns:
            dict: 回退到的执行条目
        """
        trace = result.get('debug_info', {}).get('execution_trace', [])
        
        if not trace:
            return None
        
        index = max(0, len(trace) - steps - 1)
        return trace[index]


class ErrorAnalyzer:
    """
    错误分析器，提供错误上下文和修复建议
    基于 hpl_runtime 的 ErrorAnalyzer
    """
    
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
    
    def _generate_basic_suggestions(self, error: Exception, 
                                   line_num: Optional[int]) -> List[str]:
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


def debug_code(code: str, file_path: Optional[str] = None,
               call_target: Optional[str] = None,
               call_args: Optional[List] = None) -> Dict[str, Any]:
    """
    便捷函数：调试执行 HPL 代码
    
    Args:
        code: HPL 源代码
        file_path: 可选的文件路径
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
    
    Returns:
        dict: 调试结果
    """
    service = get_debug_service()
    return service.debug_code(code, file_path, call_target, call_args)


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
