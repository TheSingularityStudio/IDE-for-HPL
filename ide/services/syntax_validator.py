"""
HPL语法验证服务
提供静态语法分析功能，不执行代码只检查语法
基于 HPLEngine 实现统一的验证接口
"""

import re
import logging
from typing import List, Dict, Any, Optional

# 导入核心引擎
try:
    from ide.services.hpl_engine import HPLEngine, validate_code as engine_validate_code
    _engine_available = True
except ImportError:
    _engine_available = False

# 导入调试服务
try:
    from ide.services.debug_service import get_error_analyzer
    _debug_service_available = True
except ImportError:
    _debug_service_available = False

logger = logging.getLogger(__name__)


class SyntaxErrorInfo:
    """语法错误信息类（保持向后兼容）"""
    
    def __init__(self, line: int, column: int, message: str, 
                 severity: str = "error", code: Optional[str] = None):
        self.line = line
        self.column = column
        self.message = message
        self.severity = severity  # "error", "warning", "info"
        self.code = code  # 相关代码片段
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'line': self.line,
            'column': self.column,
            'message': self.message,
            'severity': self.severity,
            'code': self.code
        }


class HPLSyntaxValidator:
    """
    HPL语法验证器
    基于 HPLEngine 实现，使用 hpl_runtime 进行深度语法检查
    """
    
    def __init__(self):
        self.errors: List[SyntaxErrorInfo] = []
        self.warnings: List[SyntaxErrorInfo] = []
        self._engine: Optional[HPLEngine] = None
        
        # 初始化引擎
        if _engine_available:
            try:
                self._engine = HPLEngine()
            except ImportError:
                logger.warning("HPLEngine 初始化失败")
    
    def validate(self, code: str) -> Dict[str, Any]:
        """
        验证HPL代码语法
        
        Args:
            code: HPL代码字符串
            
        Returns:
            dict: 包含errors和warnings的验证结果
        """
        self.errors = []
        self.warnings = []
        
        if not _engine_available or not self._engine:
            # 引擎不可用，返回基本错误
            self.errors.append(SyntaxErrorInfo(
                line=1, column=1,
                message="hpl_runtime 不可用，无法进行语法验证",
                severity="error"
            ))
            return {
                'valid': False,
                'errors': [e.to_dict() for e in self.errors],
                'warnings': [],
                'total_errors': 1,
                'total_warnings': 0
            }
        
        try:
            # 使用 HPLEngine 进行验证
            self._engine.load_code(code)
            diagnostics = self._engine.validate()
            
            # 转换诊断信息
            for d in diagnostics:
                info = SyntaxErrorInfo(
                    line=d.line,
                    column=d.column,
                    message=d.message,
                    severity=d.severity,
                    code=d.code
                )
                
                if d.severity == 'error':
                    self.errors.append(info)
                else:
                    self.warnings.append(info)
            
        except Exception as e:
            logger.error(f"语法验证过程出错: {e}")
            self.errors.append(SyntaxErrorInfo(
                line=1, column=1,
                message=f"验证过程出错: {str(e)}",
                severity="error"
            ))
        
        return {
            'valid': len(self.errors) == 0,
            'errors': [e.to_dict() for e in self.errors],
            'warnings': [w.to_dict() for w in self.warnings],
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings)
        }


# 全局验证器实例
_validator = None


def get_validator() -> HPLSyntaxValidator:
    """获取全局验证器实例"""
    global _validator
    if _validator is None:
        _validator = HPLSyntaxValidator()
    return _validator


def validate_code(code: str, use_runtime: bool = True) -> Dict[str, Any]:
    """
    验证HPL代码语法的便捷函数
    
    Args:
        code: HPL代码字符串
        use_runtime: 是否使用hpl_runtime进行深度检查（默认True）
        
    Returns:
        dict: 验证结果
    """
    validator = get_validator()
    return validator.validate(code)


def validate_with_suggestions(code: str) -> Dict[str, Any]:
    """
    验证代码并提供修复建议
    
    Args:
        code: HPL代码字符串
        
    Returns:
        dict: 包含验证结果和修复建议
    """
    result = validate_code(code, use_runtime=True)
    
    # 收集所有建议
    suggestions = []
    for warning in result.get('warnings', []):
        if '建议:' in warning.get('message', ''):
            suggestions.append(warning['message'].replace('建议: ', ''))
    
    result['suggestions'] = suggestions
    return result


def get_error_details(code: str, line: int, column: int) -> Optional[Dict[str, Any]]:
    """
    获取指定位置的错误详情
    
    Args:
        code: HPL代码字符串
        line: 行号（1-based）
        column: 列号（1-based）
        
    Returns:
        dict: 错误详情，如果没有则返回None
    """
    result = validate_code(code)
    
    # 查找指定位置的错误
    for error in result.get('errors', []):
        if error.get('line') == line:
            return {
                'line': line,
                'column': column,
                'message': error.get('message'),
                'severity': error.get('severity'),
                'code': error.get('code'),
                'suggestions': []
            }
    
    return None
