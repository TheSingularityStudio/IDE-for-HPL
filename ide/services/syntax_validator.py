"""
HPL语法验证服务
提供静态语法分析功能，不执行代码只检查语法
集成 hpl_runtime 进行深度语法检查
"""

import re
import logging
from typing import List, Dict, Any, Optional

# 导入调试服务
try:
    from ide.services.debug_service import get_error_analyzer
    _debug_service_available = True
except ImportError:
    _debug_service_available = False

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
    
    # HPL关键字 (基于YAML的HPL语言)
    KEYWORDS = {
        'includes', 'imports', 'classes', 'objects', 'main', 'call',
        'if', 'else', 'for', 'while', 'return', 'break', 'continue',
        'try', 'catch', 'echo', 'this', 'true', 'false', 'null',
        'and', 'or', 'not', 'is', 'in', 'len', 'type', 'int', 'str',
        'abs', 'max', 'min', 'parent'
    }
    
    # HPL内置函数
    BUILTIN_FUNCTIONS = {
        'echo', 'len', 'type', 'int', 'str', 'abs', 'max', 'min'
    }
    
    # HPL操作符
    OPERATORS = {
        '+', '-', '*', '/', '%', '==', '!=', '<', '>', '<=', '>=',
        '&&', '||', '!', '++', '='
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
        """检查HPL基本YAML结构"""
        lines = code.split('\n')
        
        # 检查是否为空文件或只有空白字符
        if not code.strip():
            self.errors.append(SyntaxErrorInfo(
                line=1,
                column=1,
                message="文件为空",
                severity="error"
            ))
            return
        
        # 检查是否只有注释（没有实际代码）
        has_actual_code = False
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                has_actual_code = True
                break
        
        if not has_actual_code:
            self.errors.append(SyntaxErrorInfo(
                line=1,
                column=1,
                message="文件为空或只包含注释",
                severity="error"
            ))
            return
        
        # 检查是否包含Tab字符（YAML不允许）
        # 但首先检查是否是混合缩进（Tab和空格都用）
        for i, line in enumerate(lines, 1):
            if not line.strip() or line.strip().startswith('#'):
                continue
            
            leading_whitespace = line[:len(line) - len(line.lstrip())]
            has_tab = '\t' in leading_whitespace
            has_space = ' ' in leading_whitespace
            
            # 如果是混合缩进，添加警告而不是错误
            if has_tab and has_space:
                self.warnings.append(SyntaxErrorInfo(
                    line=i,
                    column=1,
                    message="混合使用Tab和空格缩进，建议统一使用空格",
                    severity="warning",
                    code=line
                ))
                # 继续检查其他行，不返回
        
        # 检查纯Tab缩进（错误）
        for i, line in enumerate(lines, 1):
            if '\t' in line and line.strip() and not line.strip().startswith('#'):
                leading_whitespace = line[:len(line) - len(line.lstrip())]
                has_tab = '\t' in leading_whitespace
                has_space = ' ' in leading_whitespace
                # 只有纯Tab缩进（没有空格混合）才报错
                if has_tab and not has_space:
                    self.errors.append(SyntaxErrorInfo(
                        line=i,
                        column=1,
                        message="YAML格式错误：不能使用Tab字符缩进，请使用空格",
                        severity="error",
                        code=line
                    ))
                    return


        
        # 检查顶级键
        top_level_keys = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # 检查是否是顶级键（无缩进）
            if line[0] not in ' \t' and ':' in stripped:
                key = stripped.split(':')[0].strip()
                top_level_keys.append((i, key))

        
        # 验证必要的顶级键
        valid_keys = {'includes', 'imports', 'classes', 'objects', 'main', 'call'}
        found_keys = {key for _, key in top_level_keys}
        
        # 检查call格式（call可以调用任意函数）
        self._check_call_statement(lines)
        
        # 当既没有main也没有call时，给出提示
        if 'main' not in found_keys and 'call' not in found_keys:
            self.warnings.append(SyntaxErrorInfo(
                line=1,
                column=1,
                message="没有定义main函数或call语句，程序不会执行任何操作",
                severity="info"
            ))

        
        # 检查includes和imports格式
        self._check_includes_section(lines)
        self._check_imports_section(lines)
        
        # 检查classes格式
        self._check_classes_section(lines)
        
        # 检查objects格式
        self._check_objects_section(lines)
    
    def _check_call_statement(self, lines: List[str]):
        """检查call语句格式（支持调用任意函数）"""
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('call:'):
                # 检查格式是否为 call: functionName() 或 call: functionName(args)
                call_match = re.match(r'^call:\s*(\w+)\s*\(([^)]*)\)\s*$', stripped)
                if not call_match:
                    self.errors.append(SyntaxErrorInfo(
                        line=i,
                        column=1,
                        message="call语句格式错误，应为: call: functionName() 或 call: functionName(args)",
                        severity="error",
                        code=line
                    ))


    
    def _check_includes_section(self, lines: List[str]):
        """检查includes部分"""
        in_includes = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if stripped == 'includes:':
                in_includes = True
                continue
            elif in_includes:
                if not stripped or stripped.startswith('#'):
                    continue
                if stripped.startswith('-'):
                    # 提取include文件名（去除行尾注释）
                    include_part = stripped[1:].strip()
                    # 去除注释
                    if '#' in include_part:
                        include_part = include_part[:include_part.index('#')].strip()
                    
                    if not include_part:
                        self.errors.append(SyntaxErrorInfo(
                            line=i,
                            column=line.index('-') + 1,
                            message="include项不能为空",
                            severity="error",
                            code=line
                        ))
                    elif not include_part.endswith('.hpl'):
                        self.warnings.append(SyntaxErrorInfo(
                            line=i,
                            column=line.index('-') + 1,
                            message=f"包含文件'{include_part}'建议使用.hpl扩展名",
                            severity="warning",
                            code=line
                        ))
                elif ':' in stripped and not stripped.startswith('-'):
                    # 新的顶级键，includes部分结束
                    in_includes = False

    
    def _check_imports_section(self, lines: List[str]):
        """检查imports部分"""
        in_imports = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if stripped == 'imports:':
                in_imports = True
                continue
            elif in_imports:
                if not stripped or stripped.startswith('#'):
                    continue
                if stripped.startswith('-'):
                    # 检查是否是别名格式: - module: alias
                    import_part = stripped[1:].strip()
                    if ':' in import_part:
                        # 别名格式
                        parts = import_part.split(':')
                        if len(parts) != 2:
                            self.errors.append(SyntaxErrorInfo(
                                line=i,
                                column=line.index('-') + 1,
                                message="import别名格式错误，应为: - module: alias",
                                severity="error",
                                code=line
                            ))
                elif ':' in stripped and not stripped.startswith('-'):
                    in_imports = False
    
    def _check_classes_section(self, lines: List[str]):
        """检查classes部分"""
        in_classes = False
        current_class = None
        class_indent = 0
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # 计算缩进级别
            indent = len(line) - len(line.lstrip())
            
            if stripped == 'classes:':
                in_classes = True
                class_indent = indent
                continue
            
            if in_classes:
                # 检查是否是新的顶级键（结束classes）
                if indent == class_indent and ':' in stripped:
                    if stripped.split(':')[0].strip() in {'includes', 'imports', 'objects', 'main', 'call'}:
                        in_classes = False
                        continue
                
                # 类定义应该是classes下一级
                if indent == class_indent + 2 and ':' in stripped:
                    class_name = stripped.split(':')[0].strip()
                    # 检查类名是否有效
                    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
                        self.errors.append(SyntaxErrorInfo(
                            line=i,
                            column=indent + 1,
                            message=f"类名'{class_name}'无效，类名必须以字母或下划线开头",
                            severity="error",
                            code=line
                        ))
                    current_class = class_name
                
                # 检查parent声明
                if indent == class_indent + 4 and stripped.startswith('parent:'):
                    parent_class = stripped.split(':')[1].strip()
                    if not parent_class:
                        self.errors.append(SyntaxErrorInfo(
                            line=i,
                            column=line.index('parent:') + 1,
                            message="parent声明不能为空",
                            severity="error",
                            code=line
                        ))
                
                # 检查方法定义（箭头函数或普通方法）
                if indent == class_indent + 4 and ':' in stripped:
                    # 检查是否是箭头函数格式
                    method_pattern = r'^(\w+)\s*:'
                    method_match = re.match(method_pattern, stripped)
                    if method_match:
                        # 检查是否包含 =>
                        if '=>' not in stripped:
                            # 检查是否是 methodName: (params) { 格式（缺少 =>）
                            no_arrow_pattern = r'^(\w+)\s*:\s*\([^)]*\)\s*\{'
                            no_arrow_match = re.match(no_arrow_pattern, stripped)
                            if no_arrow_match:
                                self.errors.append(SyntaxErrorInfo(
                                    line=i,
                                    column=indent + 1,
                                    message="箭头函数语法错误，缺少 =>，应为: methodName: (params) => { code }",
                                    severity="error",
                                    code=line
                                ))
                        else:
                            self._check_arrow_function(i, line, stripped, indent)

    
    def _check_objects_section(self, lines: List[str]):
        """检查objects部分"""
        in_objects = False
        objects_indent = 0
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            indent = len(line) - len(line.lstrip())
            
            if stripped == 'objects:':
                in_objects = True
                objects_indent = indent
                continue
            
            if in_objects:
                # 检查是否是新的顶级键
                if indent == objects_indent and ':' in stripped:
                    key = stripped.split(':')[0].strip()
                    if key in {'includes', 'imports', 'classes', 'main', 'call'}:
                        in_objects = False
                        continue
                
                # 对象定义应该是objects下一级
                if indent == objects_indent + 2 and ':' in stripped:
                    # 格式: objectName: ClassName() 或 objectName: ClassName
                    obj_match = re.match(r'^(\w+)\s*:\s*(\w+)\s*(?:\(([^)]*)\))?\s*$', stripped)
                    if not obj_match:
                        self.errors.append(SyntaxErrorInfo(
                            line=i,
                            column=indent + 1,
                            message="对象定义格式错误，应为: objectName: ClassName() 或 objectName: ClassName",
                            severity="error",
                            code=line
                        ))

    
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
            
            # 检查是否同时包含Tab和空格
            has_tab = '\t' in leading_whitespace
            has_space = ' ' in leading_whitespace
            
            if has_tab and has_space:
                self.warnings.append(SyntaxErrorInfo(
                    line=i,
                    column=1,
                    message="混合使用Tab和空格缩进，建议统一使用空格",
                    severity="warning",
                    code=line
                ))

    
    def _check_arrow_function(self, line_num: int, line: str, stripped: str, indent: int):
        """检查箭头函数语法: methodName: (params) => { code }"""
        # 首先检查是否包含箭头 =>
        if '=>' not in stripped:
            # 检查是否是方法定义但没有箭头 (methodName: (params) { ... })
            method_no_arrow = re.match(r'^(\w+)\s*:\s*\(([^)]*)\)\s*\{', stripped)
            if method_no_arrow:
                self.errors.append(SyntaxErrorInfo(
                    line=line_num,
                    column=indent + 1,
                    message="箭头函数语法错误，缺少 =>，应为: methodName: (params) => { code }",
                    severity="error",
                    code=line
                ))
                return
        
        # 提取方法名
        method_match = re.match(r'^(\w+)\s*:\s*\(([^)]*)\)\s*=>\s*(?:\{.*)?$', stripped)
        if not method_match:
            # 可能是多行箭头函数
            method_match = re.match(r'^(\w+)\s*:\s*\(([^)]*)\)\s*=>\s*$', stripped)
            if not method_match:
                self.errors.append(SyntaxErrorInfo(
                    line=line_num,
                    column=indent + 1,
                    message="箭头函数语法错误，应为: methodName: (params) => { code } 或 methodName: (params) =>",
                    severity="error",
                    code=line
                ))
                return
        
        method_name = method_match.group(1)
        params = method_match.group(2)
        
        # 检查方法名
        if not re.match(r'^[a-z_][a-z0-9_]*$', method_name):
            self.warnings.append(SyntaxErrorInfo(
                line=line_num,
                column=indent + 1,
                message=f"方法名'{method_name}'建议使用小写字母开头",
                severity="warning",
                code=line
            ))
        
        # 检查参数
        if params.strip():
            param_list = [p.strip() for p in params.split(',')]
            for param in param_list:
                if not re.match(r'^[a-z_][a-z0-9_]*$', param):
                    self.errors.append(SyntaxErrorInfo(
                        line=line_num,
                        column=line.find(param) + 1,
                        message=f"参数名'{param}'无效",
                        severity="error",
                        code=line
                    ))

    
    def _check_syntax_rules(self, code: str):
        """检查HPL特定语法规则"""
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # 检查控制流语句
            if stripped.startswith('if '):
                self._check_if_statement(i, line, stripped)
            elif stripped.startswith('for '):
                self._check_for_statement(i, line, stripped)
            elif stripped.startswith('while '):
                self._check_while_statement(i, line, stripped)
            elif stripped.startswith('try'):
                self._check_try_statement(i, line, stripped)
            elif stripped.startswith('catch '):
                self._check_catch_statement(i, line, stripped)
            elif stripped.startswith('else'):
                self._check_else_statement(i, line, stripped)
            
            # 检查echo语句
            elif stripped.startswith('echo'):
                self._check_echo_statement(i, line, stripped)
            
            # 检查return语句
            elif stripped.startswith('return'):
                self._check_return_statement(i, line, stripped)
            
            # 检查break/continue
            elif stripped in {'break', 'continue'} or stripped.startswith('break ') or stripped.startswith('continue '):
                self._check_loop_control(i, line, stripped)
            
            # 检查赋值语句（包括数组赋值）
            elif '=' in stripped and not any(op in stripped for op in ['==', '!=', '<=', '>=']):
                self._check_assignment(i, line, stripped)
            
            # 检查方法调用
            elif '.' in stripped and '(' in stripped:
                self._check_method_call(i, line, stripped)
            
            # 检查数组访问
            elif '[' in stripped and ']' in stripped:
                self._check_array_access(i, line, stripped)


    
    def _check_if_statement(self, line_num: int, line: str, stripped: str):
        """检查if语句语法: if (condition) :"""
        # HPL使用: if (condition) :  (允许行尾注释)
        pattern = r'^if\s+\((.+)\)\s*:\s*(?:#.*)?$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('if') + 1,
                message="if语句语法错误，正确格式: if (condition) :",
                severity="error",
                code=line
            ))

    
    def _check_for_statement(self, line_num: int, line: str, stripped: str):
        """检查for循环语法: for (init; cond; incr) :"""
        # HPL使用C风格for循环: for (i = 0; i < count; i++) :  (允许行尾注释)
        pattern = r'^for\s+\(([^;]*);\s*([^;]*);\s*([^)]*)\)\s*:\s*(?:#.*)?$'
        match = re.match(pattern, stripped)
        
        if not match:
            # 也支持for-in风格
            pattern_in = r'^for\s+\(([^)]+)\)\s*:\s*(?:#.*)?$'
            match_in = re.match(pattern_in, stripped)
            if not match_in:
                self.errors.append(SyntaxErrorInfo(
                    line=line_num,
                    column=line.index('for') + 1,
                    message="for循环语法错误，正确格式: for (init; condition; increment) :",
                    severity="error",
                    code=line
                ))

    
    def _check_while_statement(self, line_num: int, line: str, stripped: str):
        """检查while循环语法: while (condition) :"""
        pattern = r'^while\s+\((.+)\)\s*:\s*(?:#.*)?$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('while') + 1,
                message="while循环语法错误，正确格式: while (condition) :",
                severity="error",
                code=line
            ))

    
    def _check_try_statement(self, line_num: int, line: str, stripped: str):
        """检查try语句语法: try :"""
        # 检查是否是纯try语句（后面可以有冒号或注释）
        # try后面不能有其他内容（除了可选的冒号和注释）
        if not re.match(r'^try\s*(?::\s*(?:#.*)?)?$', stripped):
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=1,
                message="try语句格式错误，应为: try :",
                severity="error",
                code=line
            ))


    
    def _check_catch_statement(self, line_num: int, line: str, stripped: str):
        """检查catch语句语法: catch (error) :"""
        pattern = r'^catch\s+\((\w+)\)\s*:\s*(?:#.*)?$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('catch') + 1,
                message="catch语句语法错误，正确格式: catch (error) :",
                severity="error",
                code=line
            ))

    
    def _check_else_statement(self, line_num: int, line: str, stripped: str):
        """检查else语句语法: else :"""
        # 检查是否是纯else语句（后面可以有冒号或注释）
        # else后面不能有其他内容（除了可选的冒号和注释）
        if not re.match(r'^else\s*(?::\s*(?:#.*)?)?$', stripped):
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=1,
                message="else语句格式错误，应为: else :",
                severity="error",
                code=line
            ))


    
    def _check_echo_statement(self, line_num: int, line: str, stripped: str):
        """检查echo语句语法: echo value 或 echo expression"""
        # echo支持: echo "string", echo variable, echo "str" + var
        # 检查echo后面是否有内容（必须有空格和表达式）
        if stripped == 'echo':
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('echo') + 1 if 'echo' in line else 1,
                message="echo语句语法错误",
                severity="error",
                code=line
            ))


    
    def _check_return_statement(self, line_num: int, line: str, stripped: str):
        """检查return语句语法: return value 或 return"""
        pattern = r'^return(?:\s+(.+))?$'
        match = re.match(pattern, stripped)
        
        if not match:
            self.errors.append(SyntaxErrorInfo(
                line=line_num,
                column=line.index('return') + 1,
                message="return语句语法错误",
                severity="error",
                code=line
            ))
    
    def _check_loop_control(self, line_num: int, line: str, stripped: str):
        """检查break/continue语句"""
        if stripped not in {'break', 'continue'}:
            # 检查是否有额外的内容
            if not re.match(r'^(break|continue)\s*$', stripped):
                self.errors.append(SyntaxErrorInfo(
                    line=line_num,
                    column=1,
                    message="break/continue语句格式错误，应为单独的break或continue",
                    severity="error",
                    code=line
                ))

    
    def _check_assignment(self, line_num: int, line: str, stripped: str):
        """检查赋值语句"""
        # 排除比较运算符
        if any(op in stripped for op in ['==', '!=', '<=', '>=']):
            return
        
        # 检查是否是数组元素赋值: arr[index] = value
        array_pattern = r'^(\w+)\s*\[([^\]]+)\]\s*=\s*(.+)$'
        array_match = re.match(array_pattern, stripped)
        if array_match:
            return  # 数组赋值是合法的
        
        # 普通赋值: var = value
        pattern = r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$'
        match = re.match(pattern, stripped)
        
        if not match:
            # 可能是复合赋值或其他情况
            pass
    
    def _check_array_access(self, line_num: int, line: str, stripped: str):
        """检查数组访问语法: arr[index]"""
        # 检查数组访问或数组元素赋值
        pattern = r'^(\w+)\s*\[([^\]]+)\]\s*(?:=\s*(.+))?$'
        match = re.match(pattern, stripped)
        
        if match:
            index = match.group(2).strip()
            # 检查索引是否为有效的表达式
            if not re.match(r'^\w+$|^\d+$|^\w+\s*[\+\-]\s*\d+$', index):
                # 复杂的索引表达式，基本检查通过
                pass

    
    def _check_method_call(self, line_num: int, line: str, stripped: str):
        """检查方法调用语法: object.method(args) 或 this.method(args)"""
        # 支持: obj.method(), this.method(), obj.method(args), module.func()
        pattern = r'^((?:this\.)?\w+(?:\.\w+)*)\s*\(([^)]*)\)\s*$'
        match = re.match(pattern, stripped)
        
        if not match:
            # 可能是链式调用或其他复杂情况
            # 只检查括号匹配
            if stripped.count('(') != stripped.count(')'):
                self.errors.append(SyntaxErrorInfo(
                    line=line_num,
                    column=line.index('(') + 1 if '(' in line else 1,
                    message="方法调用括号不匹配",
                    severity="error",
                    code=line
                ))

    
    def _check_with_runtime(self, code: str):
        """尝试使用hpl_runtime进行深度解析（如果可用）"""
        # 如果已经有错误（如Tab字符错误），跳过运行时检查
        if self.errors:
            return
            
        try:
            # 尝试导入hpl_runtime
            import sys
            import os
            import tempfile
            
            # 添加examples目录到路径
            examples_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'examples')
            if examples_dir not in sys.path:
                sys.path.insert(0, examples_dir)
            
            # 从hpl_runtime导入
            from hpl_runtime import HPLParser, HPLSyntaxError, HPLRuntimeError
            
            # 创建临时文件（使用UTF-8编码）
            with tempfile.NamedTemporaryFile(mode='w', suffix='.hpl', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name

            
            try:
                # 尝试解析
                parser = HPLParser(temp_file)
                parser.parse()
                
            except HPLSyntaxError as e:
                # 捕获HPL语法错误 - 使用详细的错误信息
                # 忽略包含文件不存在的错误（在验证阶段不需要实际文件存在）
                error_msg = e.message or str(e)
                if "not found" in error_msg.lower() and ("include" in error_msg.lower() or "import" in error_msg.lower()):
                    # 包含文件不存在，作为警告而不是错误
                    self.warnings.append(SyntaxErrorInfo(
                        line=e.line or 1,
                        column=e.column or 1,
                        message=f"警告: {error_msg}",
                        severity="warning",
                        code=self._get_code_at_line(code, e.line) if e.line else None
                    ))
                else:
                    error_info = SyntaxErrorInfo(
                        line=e.line or 1,
                        column=e.column or 1,
                        message=error_msg,
                        severity="error",
                        code=self._get_code_at_line(code, e.line) if e.line else None
                    )
                    
                    # 添加错误键（如果有）
                    if hasattr(e, 'error_key') and e.error_key:
                        error_info.message = f"[{e.error_key}] {error_info.message}"
                    
                    self.errors.append(error_info)

                
                # 如果有错误分析器，获取修复建议
                if _debug_service_available:
                    try:
                        analyzer = get_error_analyzer()
                        analysis = analyzer.analyze_error(e, code)
                        if analysis.get('suggestions'):
                            for suggestion in analysis['suggestions']:
                                self.warnings.append(SyntaxErrorInfo(
                                    line=e.line or 1,
                                    column=1,
                                    message=f"建议: {suggestion}",
                                    severity="info"
                                ))
                    except Exception as analysis_error:
                        logger.debug(f"错误分析失败: {analysis_error}")
                
            except SyntaxError as e:
                # 捕获Python语法错误（可能是HPL解析器内部错误）
                # 忽略YAML相关的Tab错误（我们已经在前面检查了）
                if "tab" in str(e).lower():
                    pass  # 已经处理过了
                else:
                    self.errors.append(SyntaxErrorInfo(
                        line=e.lineno or 1,
                        column=e.offset or 1,
                        message=str(e),
                        severity="error",
                        code=e.text
                    ))
                
            except HPLRuntimeError as e:
                # 运行时错误（在解析阶段不应该出现，但以防万一）
                self.errors.append(SyntaxErrorInfo(
                    line=e.line or 1,
                    column=e.column or 1,
                    message=f"运行时错误: {e.message}",
                    severity="error"
                ))
                
            except Exception as e:
                # 其他解析错误
                error_msg = str(e)
                # 忽略YAML相关的Tab错误和块映射错误（这些通常是缩进问题）
                if ("tab" in error_msg.lower() or 
                    "cannot start any token" in error_msg.lower() or
                    "block mapping" in error_msg.lower() or
                    "expected <block end>" in error_msg.lower()):
                    pass  # 已经处理过了或缩进问题已在前面检查
                else:
                    # 尝试从错误消息中提取行号
                    line_match = re.search(r'line\s+(\d+)', error_msg, re.IGNORECASE)
                    line_num = int(line_match.group(1)) if line_match else 1
                    
                    # 尝试从异常对象获取行号
                    if hasattr(e, 'line') and e.line:
                        line_num = e.line
                    elif hasattr(e, 'lineno') and e.lineno:
                        line_num = e.lineno
                    
                    self.errors.append(SyntaxErrorInfo(
                        line=line_num,
                        column=getattr(e, 'column', getattr(e, 'offset', 1)),
                        message=error_msg,
                        severity="error",
                        code=self._get_code_at_line(code, line_num)
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

    
    def _get_code_at_line(self, code: str, line_num: int) -> Optional[str]:
        """获取指定行的代码"""
        if not line_num or line_num < 1:
            return None
        
        lines = code.split('\n')
        if line_num <= len(lines):
            return lines[line_num - 1]
        return None



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
    result = validator.validate(code)
    
    # 如果需要，使用hpl_runtime进行额外检查
    if use_runtime and _debug_service_available:
        try:
            # 已经通过_check_with_runtime检查了，这里可以添加额外的分析
            pass
        except Exception as e:
            logger.debug(f"额外运行时检查失败: {e}")
    
    return result


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
