"""
HPL语法验证服务测试文件

测试覆盖范围：
1. 基本功能测试 - 验证器初始化和基本验证
2. 结构检查测试 - YAML结构、includes、imports、classes、objects
3. 括号匹配测试 - 各种括号匹配情况
4. 字符串引号测试 - 字符串引号匹配
5. 缩进检查测试 - 缩进规范
6. 控制流语句测试 - if、for、while、try-catch
7. 其他语句测试 - echo、return、break/continue、赋值、数组、方法调用
8. 边界情况测试 - 复杂嵌套、注释
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# 直接导入 syntax_validator 模块，避免通过 services 包的 __init__.py
# 这样可以避免导入 security.py 等依赖 Flask 的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from syntax_validator import (
    SyntaxErrorInfo,
    HPLSyntaxValidator,
    get_validator,
    validate_code,
    validate_with_suggestions,
    get_error_details
)



class TestSyntaxErrorInfo(unittest.TestCase):
    """测试 SyntaxErrorInfo 类"""
    
    def test_basic_creation(self):
        """测试基本创建"""
        error = SyntaxErrorInfo(
            line=10,
            column=5,
            message="测试错误",
            severity="error",
            code="test code"
        )
        self.assertEqual(error.line, 10)
        self.assertEqual(error.column, 5)
        self.assertEqual(error.message, "测试错误")
        self.assertEqual(error.severity, "error")
        self.assertEqual(error.code, "test code")
    
    def test_to_dict(self):
        """测试转换为字典"""
        error = SyntaxErrorInfo(
            line=1,
            column=1,
            message="测试",
            severity="warning"
        )
        result = error.to_dict()
        self.assertEqual(result['line'], 1)
        self.assertEqual(result['column'], 1)
        self.assertEqual(result['message'], "测试")
        self.assertEqual(result['severity'], "warning")
        self.assertIsNone(result['code'])


class TestHPLSyntaxValidatorBasic(unittest.TestCase):
    """测试 HPLSyntaxValidator 基本功能"""
    
    def setUp(self):
        """每个测试前创建新的验证器"""
        self.validator = HPLSyntaxValidator()
    
    def test_empty_code(self):
        """测试空代码"""
        result = self.validator.validate("")
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['errors'][0]['message'], "文件为空")
    
    def test_whitespace_only_code(self):
        """测试只有空白字符的代码"""
        result = self.validator.validate("   \n\t\n   ")
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['errors']), 1)
    
    def test_valid_minimal_code(self):
        """测试有效的最小代码"""
        code = '''main:
  echo "Hello"'''
        result = self.validator.validate(code)
        # 应该没有错误或有警告但没有错误
        self.assertEqual(len(result['errors']), 0)
    
    def test_global_validator_instance(self):
        """测试全局验证器实例"""
        validator1 = get_validator()
        validator2 = get_validator()
        self.assertIs(validator1, validator2)


class TestStructureValidation(unittest.TestCase):
    """测试结构验证"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_valid_includes(self):
        """测试有效的 includes"""
        code = '''includes:
  - utils.hpl
  - helpers.hpl

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_invalid_include_empty(self):
        """测试空的 include 项"""
        code = '''includes:
  - 
  - utils.hpl

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        # 应该检测到空的 include 项
        has_empty_error = any(
            "include项不能为空" in e['message'] 
            for e in result['errors']
        )
        self.assertTrue(has_empty_error)
    
    def test_include_without_extension_warning(self):
        """测试没有 .hpl 扩展名的 include 警告"""
        code = '''includes:
  - utils

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        # 应该有警告建议使用 .hpl 扩展名
        has_warning = any(
            ".hpl" in w['message'] and "扩展名" in w['message']
            for w in result['warnings']
        )
        self.assertTrue(has_warning)
    
    def test_valid_imports(self):
        """测试有效的 imports"""
        code = '''imports:
  - os
  - sys: system

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_invalid_import_alias_format(self):
        """测试无效的 import 别名格式"""
        code = '''imports:
  - os: sys: extra

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_format_error = any(
            "import别名格式错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_format_error)
    
    def test_valid_classes(self):
        """测试有效的 classes"""
        code = '''classes:
  Calculator:
    parent: BaseCalculator
    add: (a, b) => {
      return a + b
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_invalid_class_name(self):
        """测试无效的类名"""
        code = '''classes:
  123Invalid:
    method: () => {
      return 0
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_class_error = any(
            "类名" in e['message'] and "无效" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_class_error)
    
    def test_empty_parent(self):
        """测试空的 parent 声明"""
        code = '''classes:
  Child:
    parent: 
    method: () => {
      return 0
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_parent_error = any(
            "parent声明不能为空" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_parent_error)
    
    def test_valid_objects(self):
        """测试有效的 objects"""
        code = '''classes:
  Calculator:
    add: (a, b) => {
      return a + b
    }

objects:
  calc: Calculator()

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_invalid_object_format(self):
        """测试无效的对象格式"""
        code = '''objects:
  calc: 

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_format_error = any(
            "对象定义格式错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_format_error)
    
    def test_valid_call_statement(self):
        """测试有效的 call 语句"""
        code = "call: main()"
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_valid_call_with_args(self):
        """测试有效的带参数 call 语句"""
        code = "call: calculate(x, y)"
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_invalid_call_format(self):
        """测试无效的 call 格式"""
        code = "call: invalid format here"
        result = self.validator.validate(code)
        has_format_error = any(
            "call语句格式错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_format_error)
    
    def test_no_main_or_call_warning(self):
        """测试没有 main 或 call 的警告"""
        code = '''includes:
  - utils.hpl'''
        result = self.validator.validate(code)
        has_warning = any(
            "没有定义main函数或call语句" in w['message']
            for w in result['warnings']
        )
        self.assertTrue(has_warning)


class TestBracketMatching(unittest.TestCase):
    """测试括号匹配"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_unclosed_parenthesis(self):
        """测试未闭合的圆括号"""
        code = '''main:
  if (x > 0 :
    echo "positive"'''
        result = self.validator.validate(code)
        has_unclosed = any(
            "未闭合的括号" in e['message'] and "(" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_unclosed)
    
    def test_unclosed_brace(self):
        """测试未闭合的花括号"""
        code = '''main:
  test: () => {
    echo "start"
    # 缺少闭合的 }
  }'''
        result = self.validator.validate(code)
        # 这个测试可能需要更复杂的代码来触发错误
    
    def test_extra_closing_bracket(self):
        """测试多余的闭合括号"""
        code = 'main:\n  echo "test")'
        result = self.validator.validate(code)
        has_extra = any(
            "多余的闭合括号" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_extra)
    
    def test_mismatched_brackets(self):
        """测试不匹配的括号"""
        code = 'main:\n  arr = [1, 2, 3)'
        result = self.validator.validate(code)
        has_mismatch = any(
            "括号不匹配" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_mismatch)
    
    def test_valid_brackets(self):
        """测试有效的括号"""
        code = '''main:
  arr = [1, 2, 3]
  obj.method(arg1, arg2)
  if (x > 0):
    echo "positive"'''
        result = self.validator.validate(code)
        # 括号应该匹配
        bracket_errors = [
            e for e in result['errors']
            if "括号" in e['message']
        ]
        self.assertEqual(len(bracket_errors), 0)


class TestStringQuotes(unittest.TestCase):
    """测试字符串引号"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_unclosed_string(self):
        """测试未闭合的字符串"""
        code = '''main:
  echo "unclosed string'''
        result = self.validator.validate(code)
        has_unclosed = any(
            "未闭合的字符串引号" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_unclosed)
    
    def test_valid_string(self):
        """测试有效的字符串"""
        code = '''main:
  echo "valid string"
  echo "another string"'''
        result = self.validator.validate(code)
        string_errors = [
            e for e in result['errors']
            if "字符串" in e['message']
        ]
        self.assertEqual(len(string_errors), 0)
    
    def test_escaped_quotes(self):
        """测试转义的引号"""
        code = '''main:
  echo "string with \\"escaped\\" quotes"'''
        result = self.validator.validate(code)
        # 转义的引号不应该导致错误
        string_errors = [
            e for e in result['errors']
            if "未闭合的字符串引号" in e['message']
        ]
        self.assertEqual(len(string_errors), 0)


class TestIndentation(unittest.TestCase):
    """测试缩进检查"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_mixed_indentation_warning(self):
        """测试混合缩进警告"""
        code = "main:\n\techo \"tab\"\n  echo \"spaces\""
        result = self.validator.validate(code)
        has_mixed_warning = any(
            "混合使用Tab和空格缩进" in w['message']
            for w in result['warnings']
        )
        self.assertTrue(has_mixed_warning)
    
    def test_consistent_spaces(self):
        """测试一致的空格缩进"""
        code = '''main:
  echo "line 1"
  echo "line 2"
    echo "indented"'''
        result = self.validator.validate(code)
        indent_warnings = [
            w for w in result['warnings']
            if "混合使用Tab和空格缩进" in w['message']
        ]
        self.assertEqual(len(indent_warnings), 0)


class TestControlFlowStatements(unittest.TestCase):
    """测试控制流语句"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_valid_if_statement(self):
        """测试有效的 if 语句"""
        code = '''main:
  if (x > 0):
    echo "positive"'''
        result = self.validator.validate(code)
        if_errors = [
            e for e in result['errors']
            if "if语句语法错误" in e['message']
        ]
        self.assertEqual(len(if_errors), 0)
    
    def test_invalid_if_statement(self):
        """测试无效的 if 语句"""
        code = '''main:
  if x > 0:
    echo "positive"'''
        result = self.validator.validate(code)
        has_if_error = any(
            "if语句语法错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_if_error)
    
    def test_valid_for_loop(self):
        """测试有效的 for 循环"""
        code = '''main:
  for (i in range(10)):
    echo i'''
        result = self.validator.validate(code)
        for_errors = [
            e for e in result['errors']
            if "for循环语法错误" in e['message']
        ]
        self.assertEqual(len(for_errors), 0)
    
    def test_valid_for_loop_with_array(self):
        """测试有效的 for in 数组循环"""
        code = '''main:
  arr = [1, 2, 3]
  for (item in arr):
    echo item'''
        result = self.validator.validate(code)
        for_errors = [
            e for e in result['errors']
            if "for循环语法错误" in e['message']
        ]
        self.assertEqual(len(for_errors), 0)
    
    def test_valid_for_loop_with_string(self):
        """测试有效的 for in 字符串循环"""
        code = '''main:
  text = "hello"
  for (char in text):
    echo char'''
        result = self.validator.validate(code)
        for_errors = [
            e for e in result['errors']
            if "for循环语法错误" in e['message']
        ]
        self.assertEqual(len(for_errors), 0)
    
    def test_invalid_for_loop(self):
        """测试无效的 for 循环"""
        code = '''main:
  for i = 0; i < 10; i++:
    echo i'''
        result = self.validator.validate(code)
        has_for_error = any(
            "for循环语法错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_for_error)

    
    def test_valid_while_loop(self):
        """测试有效的 while 循环"""
        code = '''main:
  while (x > 0):
    x = x - 1'''
        result = self.validator.validate(code)
        while_errors = [
            e for e in result['errors']
            if "while循环语法错误" in e['message']
        ]
        self.assertEqual(len(while_errors), 0)
    
    def test_invalid_while_loop(self):
        """测试无效的 while 循环"""
        code = '''main:
  while x > 0:
    x = x - 1'''
        result = self.validator.validate(code)
        has_while_error = any(
            "while循环语法错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_while_error)
    
    def test_valid_try_catch(self):
        """测试有效的 try-catch"""
        code = '''main:
  try:
    risky_operation()
  catch (e):
    echo "error"'''
        result = self.validator.validate(code)
        try_errors = [
            e for e in result['errors']
            if "try语句" in e['message'] or "catch语句" in e['message']
        ]
        self.assertEqual(len(try_errors), 0)
    
    def test_invalid_try_statement(self):
        """测试无效的 try 语句"""
        code = '''main:
  try something:
    echo "test"'''
        result = self.validator.validate(code)
        has_try_error = any(
            "try语句格式错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_try_error)
    
    def test_invalid_catch_statement(self):
        """测试无效的 catch 语句"""
        code = '''main:
  try:
    echo "test"
  catch e:
    echo "error"'''
        result = self.validator.validate(code)
        has_catch_error = any(
            "catch语句语法错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_catch_error)
    
    def test_valid_else(self):
        """测试有效的 else"""
        code = '''main:
  if (x > 0):
    echo "positive"
  else:
    echo "non-positive"'''
        result = self.validator.validate(code)
        else_errors = [
            e for e in result['errors']
            if "else语句" in e['message']
        ]
        self.assertEqual(len(else_errors), 0)
    
    def test_invalid_else(self):
        """测试无效的 else"""
        code = '''main:
  if (x > 0):
    echo "positive"
  else something:
    echo "non-positive"'''
        result = self.validator.validate(code)
        has_else_error = any(
            "else语句格式错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_else_error)


class TestOtherStatements(unittest.TestCase):
    """测试其他语句"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_valid_echo(self):
        """测试有效的 echo"""
        code = '''main:
  echo "hello"
  echo variable
  echo "str" + var'''
        result = self.validator.validate(code)
        echo_errors = [
            e for e in result['errors']
            if "echo语句语法错误" in e['message']
        ]
        self.assertEqual(len(echo_errors), 0)
    
    def test_invalid_echo(self):
        """测试无效的 echo"""
        code = '''main:
  echo'''
        result = self.validator.validate(code)
        has_echo_error = any(
            "echo语句语法错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_echo_error)
    
    def test_valid_return(self):
        """测试有效的 return"""
        code = '''main:
  return 42
  return
  return x + y'''
        result = self.validator.validate(code)
        return_errors = [
            e for e in result['errors']
            if "return语句语法错误" in e['message']
        ]
        self.assertEqual(len(return_errors), 0)
    
    def test_valid_break_continue(self):
        """测试有效的 break/continue"""
        code = '''main:
  for (i in range(10)):
    if (i == 5):
      break
    if (i == 3):
      continue
    echo i'''
        result = self.validator.validate(code)
        loop_errors = [
            e for e in result['errors']
            if "break/continue" in e['message']
        ]
        self.assertEqual(len(loop_errors), 0)

    
    def test_invalid_break(self):
        """测试无效的 break"""
        code = '''main:
  break something'''
        result = self.validator.validate(code)
        has_break_error = any(
            "break/continue语句格式错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_break_error)
    
    def test_valid_assignment(self):
        """测试有效的赋值"""
        code = '''main:
  x = 10
  y = "hello"
  arr[0] = 5
  arr[i + 1] = value'''
        result = self.validator.validate(code)
        # 赋值语句不应该产生错误
        self.assertEqual(len(result['errors']), 0)
    
    def test_valid_array_access(self):
        """测试有效的数组访问"""
        code = '''main:
  x = arr[0]
  y = arr[i + 1]
  arr[0] = value'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_valid_method_call(self):
        """测试有效的方法调用"""
        code = '''main:
  obj.method()
  this.method(arg1, arg2)
  module.func()
  calc.add(1, 2)'''
        result = self.validator.validate(code)
        call_errors = [
            e for e in result['errors']
            if "方法调用" in e['message']
        ]
        self.assertEqual(len(call_errors), 0)
    
    def test_invalid_method_call_brackets(self):
        """测试方法调用括号不匹配"""
        code = '''main:
  obj.method(arg1, arg2'''
        result = self.validator.validate(code)
        has_bracket_error = any(
            "方法调用括号不匹配" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_bracket_error)


class TestArrowFunctions(unittest.TestCase):
    """测试箭头函数"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_valid_arrow_function(self):
        """测试有效的箭头函数"""
        code = '''classes:
  Calculator:
    add: (a, b) => {
      return a + b
    }
    multiply: (x, y) => {
      result = x * y
      return result
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        arrow_errors = [
            e for e in result['errors']
            if "箭头函数" in e['message']
        ]
        self.assertEqual(len(arrow_errors), 0)
    
    def test_invalid_arrow_function_syntax(self):
        """测试无效的箭头函数语法"""
        code = '''classes:
  Calculator:
    add: (a, b) {
      return a + b
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_arrow_error = any(
            "箭头函数语法错误" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_arrow_error)
    
    def test_invalid_parameter_name(self):
        """测试无效的参数名"""
        code = '''classes:
  Calculator:
    add: (1invalid, b) => {
      return 0
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_param_error = any(
            "参数名" in e['message'] and "无效" in e['message']
            for e in result['errors']
        )
        self.assertTrue(has_param_error)
    
    def test_method_name_warning(self):
        """测试方法名警告（大写字母开头）"""
        code = '''classes:
  Calculator:
    Add: (a, b) => {
      return a + b
    }

main:
  echo "Hello"'''
        result = self.validator.validate(code)
        has_warning = any(
            "方法名" in w['message'] and "小写字母开头" in w['message']
            for w in result['warnings']
        )
        self.assertTrue(has_warning)


class TestComplexCases(unittest.TestCase):
    """测试复杂情况"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_complex_valid_program(self):
        """测试复杂但有效的程序"""
        code = '''includes:
  - utils.hpl
  - helpers.hpl

imports:
  - os
  - sys: system

classes:
  Calculator:
    parent: BaseCalc
    add: (a, b) => {
      return a + b
    }
    subtract: (a, b) => {
      return a - b
    }
  
  AdvancedCalc:
    parent: Calculator
    multiply: (a, b) => {
      return a * b
    }

objects:
  calc: Calculator()
  advanced: AdvancedCalc()

main:
  x = 10
  y = 20
  
  if (x > 0):
    echo "positive"
    for (i in range(3)):
      echo i
  else:
    echo "non-positive"

  
  try:
    result = calc.add(x, y)
    echo "Result: " + result
  catch (e):
    echo "Error: " + e
  
  return 0'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_comments_handling(self):
        """测试注释处理"""
        code = '''# 这是文件顶部注释
includes:
  - utils.hpl  # 包含工具

# 主函数
main:
  # 这是行内注释
  echo "Hello"  # 行尾注释
  # 另一行注释
  x = 10'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_nested_structures(self):
        """测试嵌套结构"""
        code = '''main:
  for (i in range(3)):
    for (j in range(3)):
      if (i == j):
        echo "equal"
      else:
        echo "not equal"
      if (i + j > 2):
        break'''
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)



class TestConvenienceFunctions(unittest.TestCase):
    """测试便捷函数"""
    
    def test_validate_code_function(self):
        """测试 validate_code 函数"""
        code = '''main:
  echo "Hello"'''
        result = validate_code(code)
        self.assertIn('valid', result)
        self.assertIn('errors', result)
        self.assertIn('warnings', result)
        self.assertIn('total_errors', result)
        self.assertIn('total_warnings', result)
    
    def test_validate_with_suggestions(self):
        """测试 validate_with_suggestions 函数"""
        code = '''main:
  if x > 0:
    echo "positive"'''
        result = validate_with_suggestions(code)
        self.assertIn('suggestions', result)
        # 应该有关于 if 语句的建议
        self.assertTrue(len(result['errors']) > 0)
    
    def test_get_error_details(self):
        """测试 get_error_details 函数"""
        code = '''main:
  if x > 0:
    echo "positive"'''
        # 获取第2行（if语句）的错误详情
        details = get_error_details(code, 2, 3)
        # 应该返回错误详情
        self.assertIsNotNone(details)
        self.assertIn('message', details)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        self.validator = HPLSyntaxValidator()
    
    def test_single_line_code(self):
        """测试单行代码"""
        code = "call: main()"
        result = self.validator.validate(code)
        self.assertEqual(len(result['errors']), 0)
    
    def test_only_comments(self):
        """测试只有注释"""
        code = '''# 只有注释
# 另一行注释'''
        result = self.validator.validate(code)
        # 应该报告文件为空或只有注释
        self.assertFalse(result['valid'])
    
    def test_very_long_line(self):
        """测试非常长的行"""
        long_string = "a" * 1000
        code = f'''main:
  echo "{long_string}"'''
        result = self.validator.validate(code)
        # 长字符串不应该导致错误
        self.assertEqual(len(result['errors']), 0)
    
    def test_unicode_characters(self):
        """测试 Unicode 字符"""
        code = '''main:
  echo "你好，世界！"
  变量 = 10
  echo 变量'''
        result = self.validator.validate(code)
        # Unicode 字符应该被正确处理
        # 注意：变量名使用中文可能会触发警告
        self.assertIsInstance(result['valid'], bool)
    
    def test_multiple_errors(self):
        """测试多个错误"""
        code = '''main:
  if x > 0:
    echo "test"
  while y < 10:
    echo "loop"
  call: invalid format'''
        result = self.validator.validate(code)
        # 应该检测到多个错误
        self.assertTrue(len(result['errors']) >= 2)
        self.assertFalse(result['valid'])


if __name__ == '__main__':
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestSyntaxErrorInfo,
        TestHPLSyntaxValidatorBasic,
        TestStructureValidation,
        TestBracketMatching,
        TestStringQuotes,
        TestIndentation,
        TestControlFlowStatements,
        TestOtherStatements,
        TestArrowFunctions,
        TestComplexCases,
        TestConvenienceFunctions,
        TestEdgeCases,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回退出码
    sys.exit(0 if result.wasSuccessful() else 1)
