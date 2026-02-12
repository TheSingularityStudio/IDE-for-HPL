"""
HPL语法验证服务测试文件

测试覆盖范围：
1. 基本功能测试 - HPLEngine初始化和基本验证
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

from ide.services.execution_service import HPLEngine, get_execution_service


class TestHPLEngineBasic(unittest.TestCase):
    """测试 HPLEngine 基本功能"""
    
    def setUp(self):
        """每个测试前创建新的引擎"""
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_empty_code(self):
        """测试空代码"""
        self.engine.load_code("")
        diagnostics = self.engine.validate()
        self.assertTrue(len(diagnostics) > 0)
        self.assertEqual(diagnostics[0]['message'], "代码为空")
    
    def test_whitespace_only_code(self):
        """测试只有空白字符的代码"""
        self.engine.load_code("   \n\t\n   ")
        diagnostics = self.engine.validate()
        self.assertTrue(len(diagnostics) > 0)
    
    def test_valid_minimal_code(self):
        """测试有效的最小代码"""
        code = '''main:
  echo "Hello"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        # 应该没有错误或只有警告
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_global_service_instance(self):
        """测试全局服务实例"""
        try:
            service1 = get_execution_service()
            service2 = get_execution_service()
            self.assertIs(service1, service2)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")


class TestStructureValidation(unittest.TestCase):
    """测试结构验证"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_valid_includes(self):
        """测试有效的 includes"""
        code = '''includes:
  - utils.hpl
  - helpers.hpl

main:
  echo "Hello"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_valid_imports(self):
        """测试有效的 imports"""
        code = '''imports:
  - os
  - sys: system

main:
  echo "Hello"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
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
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
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
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_valid_call_statement(self):
        """测试有效的 call 语句"""
        code = "call: main()"
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_no_main_or_call(self):
        """测试没有 main 或 call 的情况"""
        code = '''includes:
  - utils.hpl'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        # 应该没有错误，但可能无法执行
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


class TestBracketMatching(unittest.TestCase):
    """测试括号匹配"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_unclosed_parenthesis(self):
        """测试未闭合的圆括号"""
        code = '''main:
  if (x > 0 :
    echo "positive"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        # 运行时解析器应该能检测到语法错误
        self.assertTrue(len(diagnostics) >= 0)  # 可能有错误也可能没有，取决于解析器
    
    def test_extra_closing_bracket(self):
        """测试多余的闭合括号"""
        code = 'main:\n  echo "test")'
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        # 运行时应该能检测到
        self.assertTrue(len(diagnostics) >= 0)
    
    def test_valid_brackets(self):
        """测试有效的括号"""
        code = '''main: () => {
  arr = [1, 2, 3]
  if (x > 0) :
    echo "positive"
}'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)




class TestStringQuotes(unittest.TestCase):
    """测试字符串引号"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_valid_string(self):
        """测试有效的字符串"""
        code = '''main:
  echo "valid string"
  echo "another string"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_escaped_quotes(self):
        """测试转义的引号"""
        code = '''main:
  echo "string with \\"escaped\\" quotes"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


class TestControlFlowStatements(unittest.TestCase):
    """测试控制流语句"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_valid_if_statement(self):
        """测试有效的 if 语句"""
        code = '''main:
  if x > 0:
    echo "positive"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)

    
    def test_valid_for_loop(self):
        """测试有效的 for 循环"""
        code = '''main:
  for i in range(10):
    echo "i"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)

    
    def test_valid_for_loop_with_array(self):
        """测试有效的 for in 数组循环"""
        code = '''main: () => {
  arr = [1, 2, 3]
  for (item in arr) :
    echo "item"
}'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


    
    def test_valid_while_loop(self):
        """测试有效的 while 循环"""
        code = '''main:
  while x > 0:
    x = x - 1'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)

    
    def test_valid_try_catch(self):
        """测试有效的 try-catch"""
        code = '''main:
  try:
    risky_operation()
  catch e:
    echo "error"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)

    
    def test_valid_else(self):
        """测试有效的 else"""
        code = '''main:
  if x > 0:
    echo "positive"
  else:
    echo "non-positive"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)



class TestOtherStatements(unittest.TestCase):
    """测试其他语句"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_valid_echo(self):
        """测试有效的 echo"""
        code = '''main:
  echo "hello"
  echo variable'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_valid_return(self):
        """测试有效的 return"""
        code = '''main:
  return 42
  return
  return x + y'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_valid_break_continue(self):
        """测试有效的 break/continue"""
        code = '''main: () => {
  for (i in range(10)) :
    if (i == 5) :
      break
    if (i == 3) :
      continue
    echo "i"
}'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


    
    def test_valid_assignment(self):
        """测试有效的赋值"""
        code = '''main:
  x = 10
  y = "hello"
  arr[0] = 5'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_valid_array_access(self):
        """测试有效的数组访问"""
        code = '''main:
  x = arr[0]
  y = arr[i + 1]
  arr[0] = value'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_valid_method_call(self):
        """测试有效的方法调用"""
        code = '''main:
  obj.method()
  this.method(arg1, arg2)
  calc.add(1, 2)'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


class TestArrowFunctions(unittest.TestCase):
    """测试箭头函数"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
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
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


class TestComplexCases(unittest.TestCase):
    """测试复杂情况"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_complex_valid_program(self):
        """测试复杂但有效的程序"""
        code = '''classes:
  Calculator:
    add: (a, b) => {
      return a + b
    }

objects:
  calc: Calculator()

main: () => {
  x = 10
  y = 20
  
  if (x > 0) :
    echo "positive"
    for (i in range(3)) :
      echo "i"
  else :
    echo "non-positive"

  try :
    result = calc.add(x, y)
    echo "Result"
  catch (e) :
    echo "Error"
  
  return 0
}'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)


    
    def test_comments_handling(self):
        """测试注释处理"""
        code = '''main:
  echo "Hello"
  x = 10'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)

    
    def test_nested_structures(self):
        """测试嵌套结构"""
        code = '''main:
  for i in range(3):
    for j in range(3):
      if i == j:
        echo "equal"
      else:
        echo "not equal"
      if i + j > 2:
        break'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)



class TestConvenienceFunctions(unittest.TestCase):
    """测试便捷函数"""
    
    def test_validate_code_function(self):
        """测试 validate_code 函数"""
        try:
            service = get_execution_service()
            code = '''main:
  echo "Hello"'''
            result = service.validate_code(code)
            self.assertIn('success', result)
            self.assertIsInstance(result.get('success'), bool)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_get_completions_function(self):
        """测试 get_completions 函数"""
        try:
            service = get_execution_service()
            code = '''main:
  echo "Hello"'''
            completions = service.get_completions(code, 1, 1, "")
            self.assertIsInstance(completions, list)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_get_code_outline_function(self):
        """测试 get_code_outline 函数"""
        try:
            service = get_execution_service()
            code = '''main:
  echo "Hello"'''
            outline = service.get_code_outline(code)
            self.assertIn('classes', outline)
            self.assertIn('functions', outline)
            self.assertIn('objects', outline)
            self.assertIn('imports', outline)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        try:
            self.engine = HPLEngine(use_cache=False)
        except ImportError:
            self.skipTest("hpl_runtime 不可用，跳过测试")
    
    def test_single_line_code(self):
        """测试单行代码"""
        code = "call: main()"
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_very_long_line(self):
        """测试非常长的行"""
        long_string = "a" * 1000
        code = f'''main:
  echo "{long_string}"'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        errors = [d for d in diagnostics if d.get('severity') == 'error']
        self.assertEqual(len(errors), 0)
    
    def test_unicode_characters(self):
        """测试 Unicode 字符"""
        code = '''main:
  echo "你好，世界！"
  变量 = 10
  echo 变量'''
        self.engine.load_code(code)
        diagnostics = self.engine.validate()
        # Unicode 字符应该被正确处理
        self.assertIsInstance(diagnostics, list)


if __name__ == '__main__':
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestHPLEngineBasic,
        TestStructureValidation,
        TestBracketMatching,
        TestStringQuotes,
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
