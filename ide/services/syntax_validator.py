"""
HPL语法验证服务
提供静态语法分析功能，不执行代码只检查语法
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SyntaxErrorInfo:
    """语法错误信息类"""
    
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
    """HPL语法验证器"""
    
    # HPL关键字
    KEYWORDS = {
        'class', 'object', 'func', 'if', 'else', 'elif', 'for', 'while',
        'return', 'break', 'continue', 'try', 'catch', 'throw', 'new',
        'this', 'super', 'true', 'false', 'null', 'includes', 'import',
        'as', 'from', 'in', 'and', 'or', 'not', 'is', 'print', 'input'
    }
    
    # 有效的类型名
    BUILTIN_TYPES = {
        'int', 'float', 'string', 'bool', 'list', 'dict', 'void', 'any'
    }
    
    def __init__(self):
        self.errors: List[SyntaxErrorInfo] = []
        self.warnings: List[SyntaxErrorInfo] = []
        self.code_lines: List[str] = []
    
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
        self.code_lines = code.split('\n')
        
        try:
            # 1. 基本结构检查
            self._check_basic_structure(code)
            
            # 2. 括号匹配检查
            self._check_brackets(code)
            
            # 3. 字符串引号匹配检查
            self._check_string_quotes(code)
            
            # 4. 缩进检查
            self._check_indentation(code)
            
            # 5. 语法规则检查（逐行）
            self._check_syntax_rules(code)
            
            # 6. 尝试使用hpl_runtime解析（如果可用）
            self._check_with_runtime(code)
            
        except Exception as e:
            logger.error(f"语法验证过程出错: {e}")
            # 添加一个通用错误
            self.errors.append(SyntaxErrorInfo(
                line=1,
                column=1,
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
    
    def _check_basic_structure(self, code: str):
        """检查基本代码结构"""
        lines = code.split('\n')
        
        # 检查是否为空文件
        if not code.strip():
            self.errors.append(SyntaxErrorInfo(
                line=1,
                column=1,
                message="文件为空",
                severity="error"
            ))
            return
        
        # 检查includes部分格式
        in_includes = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检查includes部分
            if stripped.startswith('includes:'):
                in_includes = True
                # 检查includes后面是否有内容
                if ':' in stripped and stripped.index(':') == len(stripped) - 1:
                    # includes: 后面没有内容，检查下一行
                    pass
            elif in_includes:
                if stripped.startswith('-'):
                    # 检查include项格式
                    include_item = stripped[1:].strip()
                    if not include_item:
                        self.errors.append(SyntaxErrorInfo(
                            line=i,
                            column=line.index('-') + 1,
                            message="include项不能为空",
                            severity="error",
                            code=line
                        ))
                elif stripped and not stripped.startswith('#'):
                    # includes部分结束
                    in_includes = False
    
    def _check_brackets(self, code: str):
        """检查括号匹配"""
        stack = []
        line_num = 1
        col_num = 1
        
        brackets = {'(': ')', '[': ']', '{': '}'}
        closing = set(brackets.values())
        
        for char in code:
            if char == '\n':
                line_num += 1
                col_num = 1
                continue
            
            if char in brackets:
                stack.append((char, line_num, col_num))
            elif char in closing:
                if not stack:
                    self.errors.append(SyntaxErrorInfo(
                        line=line_num,
                        column=col_num,
                        message=f"多余的闭合括号 '{char}'",
                        severity="error"
                    ))
                else:
                    last_open, last_line, last_col = stack.pop()
                    expected = brackets[last_open]
                    if char != expected:
                        self.errors.append(SyntaxErrorInfo(
                            line=line_num,
                            column=col_num,
                            message=f"括号不匹配: 期望 '{expected}' 但找到 '{char}'",
                            severity="error"
                        ))
            
            col_num += 1
        
        # 检查未闭合的括号
        for open_bracket, line, col in stack:
            self.errors.append(SyntaxErrorInfo(
                line=line,
                column=col,
                message=f"未闭合的括号 '{open_bracket}'",
                severity="error"
            ))
    
    def _check_string_quotes(self, code: str):
        """检查字符串引号匹配"""
        in_string = False
        string_start_line = 0
        string_start_col = 0
        escape_next = False
        
        line_num = 1
        col_num = 1
        
        for i, char in enumerate(code):
            if char == '\n':
                if in_string:
                    # 字符串跨行，检查是否是三引号字符串
                    # HPL不支持三引号，所以这是错误
                    pass
                line_num += 1
                col_num = 1
                continue
            
            if escape_next:
                escape_next = False
                col_num += 1
                continue
            
            if char == '\\':
                escape_next = True
                col_num += 1
                continue
            
            if char == '"':
                if not in_string:
                    in_string = True
                    string_start_line = line_num
                    string_start_col = col_num
                else:
                    in_string = False
            
            col_num += 1
        
        if in_string:
            self.errors.append(SyntaxErrorInfo(
                line=string_start_line,
                column=string_start_col,
                message="未闭合的字符串引号",
                severity="error"
            ))
    
    def _check_indentation(self, code: str):
        """检查缩进"""
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            if not line.strip() or line.strip().startswith('#'):
                continue
            
            # 检查是否使用空格缩进（推荐）或Tab
            leading_whitespace = line[:len(line) - len(line.lstrip())]
            
            if '\t' in leading_whitespace and ' ' in leading_whitespace:
                self.warnings.append(SyntaxErrorInfo(
                    line=i,
                    column=1,
                    message="混合使用Tab和空格缩进，建议统一使用空格",
                    severity="warning",
                    code=line
                ))
    
    def _check_syntax_rules(self, code: str):
        """检查HPL特定语法规则"""
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # 检查类定义
            if stripped.startswith('class '):
                self._check_class_definition(i, line, stripped)
            
            # 检查函数定义
            elif stripped.startswith('func '):
                self._check_function_definition(i, line, stripped)
            
            # 检查对象定义
            elif stripped.startswith('object '):
                self._check_object_definition(i, line, stripped)
            
            # 检查if语句
            elif stripped.startswith('if '):
                self._check_if_statement(i, line, stripped)
            
            # 检查for循环
            elif stripped.startswith('for '):
                self._check_for_statement(i, line, stripped)
            
            # 检查赋值语句
            elif '=' in stripped and not stripped.startswith('//'):
                self._check_assignment(i, line, stripped)
            
            # 检查方法调用
            elif '.' in stripped and '(' in stripped:
                self._check_method_call(i, line, stripped)
    
    def _check_class_definition(self, line_num: int, line: str, stripped: str):
        """检查类定义语法"""
        # class ClassName(ParentClass):
        pattern = r'^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]*)\))?\s*:\s*$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('class') + 1,
                message="类定义语法错误，正确格式: class ClassName(Parent): 或 class ClassName:",
                severity="error",
                code=line
            ))
    
    def _check_function_definition(self, line_num: int, line: str, stripped: str):
        """检查函数定义语法"""
        # func functionName(param1, param2):
        # func functionName() -> returnType:
        pattern = r'^func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(?:->\s*([A-Za-z_][A-Za-z0-9_]*))?\s*:\s*$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('func') + 1,
                message="函数定义语法错误，正确格式: func name(params): 或 func name(params) -> type:",
                severity="error",
                code=line
            ))
    
    def _check_object_definition(self, line_num: int, line: str, stripped: str):
        """检查对象定义语法"""
        # object ObjectName = ClassName(params)
        pattern = r'^object\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('object') + 1,
                message="对象定义语法错误，正确格式: object Name = ClassName(params)",
                severity="error",
                code=line
            ))
    
    def _check_if_statement(self, line_num: int, line: str, stripped: str):
        """检查if语句语法"""
        # if condition:
        pattern = r'^if\s+(.+):\s*$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('if') + 1,
                message="if语句语法错误，正确格式: if condition:",
                severity="error",
                code=line
            ))
    
    def _check_for_statement(self, line_num: int, line: str, stripped: str):
        """检查for循环语法"""
        # for item in collection:
        pattern = r'^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+):\s*$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('for') + 1,
                message="for循环语法错误，正确格式: for item in collection:",
                severity="error",
                code=line
            ))
    
    def _check_assignment(self, line_num: int, line: str, stripped: str):
        """检查赋值语句"""
        # 检查是否是有效的赋值
        # 排除比较运算符 ==, !=, <=, >=
        if '==' in stripped or '!=' in stripped or '<=' in stripped or '>=' in stripped:
            return
        
        # 检查赋值语法
        # var = value
        # var: type = value
        pattern = r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*([A-Za-z_][A-Za-z0-9_]*))?\s*=\s*(.+)$'
        match = re.match(pattern, stripped)
        
        if not match:
            # 可能是复合赋值或其他情况，暂时不报错
            pass
    
    def _check_method_call(self, line_num: int, line: str, stripped: str):
        """检查方法调用语法"""
        # object.method(args)
        # 简单检查括号匹配
        if stripped.count('(') != stripped.count(')'):
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('(') + 1 if '(' in line else 1,
                message="方法调用括号不匹配",
                severity="error",
                code=line
            ))
    
    def _check_with_runtime(self, code: str):
        """尝试使用hpl_runtime进行解析（如果可用）"""
        try:
            # 尝试导入hpl_runtime
            import sys
            import os
            import tempfile
            
            # 添加examples目录到路径
            examples_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'examples')
            if examples_dir not in sys.path:
                sys.path.insert(0, examples_dir)
            
            from hpl_runtime.parser import HPLParser
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.hpl', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # 尝试解析
                parser = HPLParser(temp_file)
                parser.parse()
                
            except SyntaxError as e:
                # 捕获语法错误
                self.errors.append(SyntaxErrorInfo(
                    line=e.lineno or 1,
                    column=e.offset or 1,
                    message=str(e),
                    severity="error",
                    code=e.text
                ))
            except Exception as e:
                # 其他解析错误
                error_msg = str(e)
                # 尝试从错误消息中提取行号
                line_match = re.search(r'line\s+(\d+)', error_msg, re.IGNORECASE)
                line_num = int(line_match.group(1)) if line_match else 1
                
                self.errors.append(SyntaxErrorInfo(
                    line=line_num,
                    column=1,
                    message=error_msg,
                    severity="error"
                ))
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except ImportError:
            # hpl_runtime不可用，使用基本检查即可
            logger.debug("hpl_runtime不可用，使用基本语法检查")
        except Exception as e:
            logger.error(f"使用hpl_runtime检查失败: {e}")


# 全局验证器实例
_validator = None


def get_validator() -> HPLSyntaxValidator:
    """获取全局验证器实例"""
    global _validator
    if _validator is None:
        _validator = HPLSyntaxValidator()
    return _validator


def validate_code(code: str) -> Dict[str, Any]:
    """
    验证HPL代码语法的便捷函数
    
    Args:
        code: HPL代码字符串
        
    Returns:
        dict: 验证结果
    """
    validator = get_validator()
    return validator.validate(code)
