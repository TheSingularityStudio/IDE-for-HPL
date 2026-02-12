"""
代码预处理服务
处理HPL代码清理和include文件管理
提供调试处理、错误上下文分析和代码补全支持
"""

import os
import re
import shutil
import logging
import tempfile
from typing import Dict, List, Any, Optional, Tuple

from config import PROJECT_ROOT, ALLOWED_EXAMPLES_DIR

# 导入调试服务
try:
    from ide.services.debug_service import get_debug_service, get_error_analyzer, HPLDebugService
    _debug_service_available = True
except ImportError:
    _debug_service_available = False

logger = logging.getLogger(__name__)



def clean_code(code):
    """
    清理代码中的转义字符
    处理 PowerShell 等发送的转义换行符
    注意：只在字符串外部处理转义，保留字符串内部的转义序列
    
    Args:
        code: 原始代码字符串
    
    Returns:
        清理后的代码字符串
    """
    result = []
    i = 0
    length = len(code)
    in_string = False
    
    while i < length:
        char = code[i]
        
        # 处理字符串边界
        if char == '"':
            # 检查是否是转义的引号
            if i > 0 and code[i - 1] == '\\':
                # 字符串内的转义引号，保留原样
                result.append(char)
                i += 1
            else:
                # 字符串边界
                in_string = not in_string
                result.append(char)
                i += 1
            continue
        
        # 如果在字符串内部，保留所有字符原样（除了继续检查字符串边界）
        if in_string:
            result.append(char)
            i += 1
            continue
        
        # 在字符串外部，处理转义字符
        # 处理 PowerShell 风格的换行符转义
        if char == '`' and i + 1 < length and code[i + 1] == 'n':
            result.append('\n')
            i += 2
        # 处理 \n 转义
        elif char == '\\' and i + 1 < length and code[i + 1] == 'n':
            result.append('\n')
            i += 2
        # 处理 \t 转义
        elif char == '\\' and i + 1 < length and code[i + 1] == 't':
            result.append('\t')
            i += 2
        # 处理 \" 转义 - 只在字符串外部时处理（创建字符串边界）
        elif char == '\\' and i + 1 < length and code[i + 1] == '"':
            # 保留转义引号，让 HPL 解析器正确处理
            result.append(char)
            result.append(code[i + 1])
            i += 2
        else:
            result.append(char)
            i += 1
    
    return ''.join(result)


def extract_includes(code):
    """
    从 HPL 代码中提取 includes 列表
    使用正则表达式解析，避免 YAML 解析错误（HPL 代码包含 => 箭头函数）
    
    Args:
        code: HPL代码字符串
    
    Returns:
        list: include文件列表
    """
    includes = []
    try:
        # 使用正则表达式匹配 includes 部分
        # 匹配 includes: 后面跟着的列表项
        
        # 查找 includes: 部分
        includes_pattern = r'^includes:\s*(?:\r?\n)((?:\s*-\s*.+\s*(?:\r?\n)?)*)'
        match = re.search(includes_pattern, code, re.MULTILINE)
        
        if match:
            # 提取列表项
            list_content = match.group(1)
            # 匹配每个 - 开头的项
            item_pattern = r'^\s*-\s*(.+?)\s*$'
            for line in list_content.split('\n'):
                item_match = re.match(item_pattern, line)
                if item_match:
                    include_file = item_match.group(1).strip()
                    # 去除可能的引号
                    include_file = include_file.strip('"\'')
                    includes.append(include_file)
    except Exception:
        # 如果解析失败，返回空列表
        pass
    return includes


def copy_include_files(code, temp_dir, base_dir=None):
    """
    复制 include 文件到临时目录
    从多个可能的目录查找 include 文件：
    1. 当前工作目录（如果指定了 base_dir）
    2. 项目根目录
    3. examples 目录
    
    Args:
        code: HPL代码
        temp_dir: 临时目录路径
        base_dir: 基础搜索目录（可选）
    
    Returns:
        tuple: (copied_files列表, 更新后的代码, 未找到的includes列表)
    """
    includes = extract_includes(code)
    if not includes:
        return [], code, []
    
    copied_files = []
    not_found = []
    
    # 定义搜索路径（按优先级）
    search_paths = []
    
    # 1. 基础目录（如果有）
    if base_dir and os.path.exists(base_dir):
        search_paths.append(os.path.abspath(base_dir))
    
    # 2. 项目根目录
    search_paths.append(PROJECT_ROOT)
    
    # 3. examples 目录
    if os.path.exists(ALLOWED_EXAMPLES_DIR):
        search_paths.append(ALLOWED_EXAMPLES_DIR)
    
    for include_file in includes:
        # 清理文件路径（防止目录遍历）
        clean_include = os.path.normpath(include_file).lstrip('/\\')
        if '..' in clean_include:
            logger.warning(f"跳过非法 include 路径: {include_file}")
            not_found.append(include_file)
            continue
        
        found = False
        for search_dir in search_paths:
            source_path = os.path.join(search_dir, clean_include)
            if os.path.exists(source_path) and os.path.isfile(source_path):
                # 复制到临时目录
                dest_path = os.path.join(temp_dir, clean_include)
                
                # 确保目标目录存在
                dest_dir = os.path.dirname(dest_path)
                if dest_dir and not os.path.exists(dest_dir):
                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                    except Exception as e:
                        logger.error(f"创建目录失败: {dest_dir}, 错误: {e}")
                        continue
                
                try:
                    shutil.copy2(source_path, dest_path)
                    copied_files.append(dest_path)
                    logger.info(f"复制 include 文件: {source_path} -> {dest_path}")
                    found = True
                    break
                except Exception as e:
                    logger.error(f"复制 include 文件失败: {source_path}, 错误: {e}")
        
        if not found:
            not_found.append(include_file)
            logger.warning(f"未找到 include 文件: {include_file}")
    
    return copied_files, code, not_found


def process_for_debug(code: str, file_path: Optional[str] = None,
                     call_target: Optional[str] = None,
                     call_args: Optional[List] = None) -> Dict[str, Any]:
    """
    处理代码用于调试执行
    清理代码、复制 include 文件，并准备调试环境
    
    Args:
        code: HPL 源代码
        file_path: 可选的文件路径（用于确定基础目录）
        call_target: 可选的调用目标函数
        call_args: 可选的调用参数
    
    Returns:
        dict: 处理结果，包含临时文件路径和调试信息
    """
    if not _debug_service_available:
        return {
            'success': False,
            'error': '调试服务不可用',
            'temp_file': None
        }
    
    try:
        # 1. 清理代码
        cleaned_code = clean_code(code)
        
        # 2. 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix='hpl_debug_')
        
        # 3. 确定基础目录
        base_dir = os.path.dirname(file_path) if file_path else None
        
        # 4. 复制 include 文件
        copied_files, _, not_found = copy_include_files(
            cleaned_code, temp_dir, base_dir
        )
        
        # 5. 创建临时 HPL 文件
        if file_path:
            temp_file_name = os.path.basename(file_path)
        else:
            temp_file_name = 'debug_temp.hpl'
        
        temp_file_path = os.path.join(temp_dir, temp_file_name)
        
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)
        
        # 6. 使用调试服务执行
        debug_service = get_debug_service()
        debug_result = debug_service.debug_file(
            temp_file_path, 
            call_target=call_target,
            call_args=call_args
        )
        
        return {
            'success': debug_result.get('success', False),
            'temp_file': temp_file_path,
            'temp_dir': temp_dir,
            'copied_includes': copied_files,
            'missing_includes': not_found,
            'debug_result': debug_result,
            'cleaned_code': cleaned_code
        }
        
    except Exception as e:
        logger.error(f"调试处理失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': f"调试处理失败: {str(e)}",
            'temp_file': None
        }


def get_error_context(code: str, error: Exception, 
                      file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    获取错误上下文和修复建议
    
    Args:
        code: HPL 源代码
        error: 异常对象
        file_path: 可选的文件路径
    
    Returns:
        dict: 错误分析结果，包含上下文行和建议
    """
    if not _debug_service_available:
        # 基础错误分析
        line_num = None
        if hasattr(error, 'lineno'):
            line_num = error.lineno
        elif hasattr(error, 'line'):
            line_num = error.line
        
        surrounding = []
        if line_num:
            lines = code.split('\n')
            start = max(0, line_num - 3 - 1)
            end = min(len(lines), line_num + 3)
            for i in range(start, end):
                surrounding.append({
                    'line_number': i + 1,
                    'content': lines[i],
                    'is_error_line': (i + 1) == line_num
                })
        
        return {
            'error_type': type(error).__name__,
            'message': str(error),
            'line': line_num,
            'surrounding_lines': surrounding,
            'suggestions': ['检查代码逻辑', '参考 HPL 语法手册'],
            'file': file_path
        }
    
    try:
        analyzer = get_error_analyzer()
        result = analyzer.analyze_error(error, code)
        result['file'] = file_path
        return result
    except Exception as e:
        logger.error(f"获取错误上下文失败: {e}")
        return {
            'error_type': type(error).__name__,
            'message': str(error),
            'line': getattr(error, 'lineno', getattr(error, 'line', None)),
            'surrounding_lines': [],
            'suggestions': ['检查代码逻辑'],
            'file': file_path,
            'analysis_error': str(e)
        }


def get_completion_items(code: str, line: int, column: int, 
                         prefix: str = "") -> List[Dict[str, Any]]:
    """
    获取代码补全项
    基于 HPL 代码解析提供类、对象、函数的补全建议
    
    Args:
        code: HPL 源代码
        line: 当前行号（1-based）
        column: 当前列号（1-based）
        prefix: 当前输入前缀
    
    Returns:
        list: 补全项列表
    """
    items = []
    
    # 尝试使用 hpl_runtime 解析代码
    try:
        import sys
        import tempfile
        
        # 添加 examples 目录到路径
        if ALLOWED_EXAMPLES_DIR not in sys.path:
            sys.path.insert(0, ALLOWED_EXAMPLES_DIR)
        
        from hpl_runtime import HPLParser
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.hpl', 
                                         delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 解析代码
            parser = HPLParser(temp_file)
            classes, objects, functions, _, _, _, _ = parser.parse()
            
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
                                        (f", 方法: {', '.join(methods)}" if methods else ""),
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
                    params = []
                    if hasattr(func, 'params'):
                        params = func.params
                    
                    # 生成带占位符的插入文本
                    param_snippets = []
                    for i, param in enumerate(params):
                        param_snippets.append(f"${{{i+1}:{param}}}")
                    
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
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
                
    except ImportError:
        logger.debug("hpl_runtime 不可用，使用基础补全")
    except Exception as e:
        logger.error(f"解析代码获取补全项失败: {e}")
    
    # 添加 HPL 关键字补全
    keywords = {
        'if': ('if (condition) :', '条件语句'),
        'else': ('else :', 'else 分支'),
        'for': ('for (init; cond; incr) :', 'for 循环'),
        'while': ('while (condition) :', 'while 循环'),
        'try': ('try :', '异常捕获'),
        'catch': ('catch (error) :', '异常处理'),
        'echo': ('echo ', '输出语句'),
        'return': ('return ', '返回语句'),
        'break': ('break', '跳出循环'),
        'continue': ('continue', '继续循环'),
        'true': ('true', '布尔真'),
        'false': ('false', '布尔假'),
        'null': ('null', '空值'),
    }
    
    for keyword, (snippet, doc) in keywords.items():
        if keyword.startswith(prefix):
            items.append({
                'label': keyword,
                'kind': 'Keyword',
                'detail': f"Keyword: {keyword}",
                'documentation': doc,
                'insertText': snippet
            })
    
    # 添加内置函数补全
    builtins = {
        'echo': ('echo ${1:value}', '输出值'),
        'len': ('len(${1:array})', '获取数组长度'),
        'type': ('type(${1:value})', '获取值类型'),
        'int': ('int(${1:value})', '转换为整数'),
        'str': ('str(${1:value})', '转换为字符串'),
        'abs': ('abs(${1:value})', '绝对值'),
        'max': ('max(${1:a}, ${2:b})', '最大值'),
        'min': ('min(${1:a}, ${2:b})', '最小值'),
    }
    
    for builtin, (snippet, doc) in builtins.items():
        if builtin.startswith(prefix):
            items.append({
                'label': builtin,
                'kind': 'Function',
                'detail': f"Builtin: {builtin}",
                'documentation': doc,
                'insertText': snippet
            })
    
    # 按标签排序
    items.sort(key=lambda x: x['label'])
    
    return items


def get_code_outline(code: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    获取代码大纲（类、函数、对象结构）
    
    Args:
        code: HPL 源代码
    
    Returns:
        dict: 代码结构大纲
    """
    outline = {
        'classes': [],
        'functions': [],
        'objects': [],
        'imports': []
    }
    
    try:
        import sys
        import tempfile
        
        # 添加 examples 目录到路径
        if ALLOWED_EXAMPLES_DIR not in sys.path:
            sys.path.insert(0, ALLOWED_EXAMPLES_DIR)
        
        from hpl_runtime import HPLParser
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.hpl', 
                                         delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            parser = HPLParser(temp_file)
            classes, objects, functions, main_func, _, _, imports = parser.parse()
            
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
                
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
                
    except Exception as e:
        logger.error(f"获取代码大纲失败: {e}")
    
    return outline
