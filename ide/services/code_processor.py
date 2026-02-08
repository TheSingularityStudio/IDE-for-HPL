"""
代码预处理服务
处理HPL代码清理和include文件管理
"""

import os
import re
import shutil
import logging
import tempfile

from config import PROJECT_ROOT, ALLOWED_EXAMPLES_DIR

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
