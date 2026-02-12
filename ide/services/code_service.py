"""
HPL 代码服务
统一处理代码处理、验证和安全检查
合并了原有的 code_processor、syntax_validator 和 security
"""

import os
import re
import shutil
import logging
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from functools import wraps
from flask import request, jsonify

from ide.config import MAX_REQUEST_SIZE, ALLOWED_EXAMPLES_DIR



logger = logging.getLogger(__name__)


# Security decorators and functions
def limit_request_size(max_size):
    """
    装饰器：限制请求大小

    Args:
        max_size: 最大允许的字节数

    Returns:
        装饰器函数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            content_length = request.content_length
            if content_length and content_length > max_size:
                logger.warning(f"请求过大: {content_length} bytes")
                return jsonify({
                    'success': False,
                    'error': f'请求大小超过限制 ({max_size} bytes)'
                }), 413
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_path(file_path, allowed_dir):
    """
    验证文件路径是否在允许的目录内
    防止路径遍历攻击

    Args:
        file_path: 要验证的文件路径
        allowed_dir: 允许的根目录

    Returns:
        验证通过的绝对路径，或None（如果验证失败）
    """
    # 规范化路径
    abs_path = os.path.abspath(file_path)
    abs_allowed = os.path.abspath(allowed_dir)

    # 使用 commonpath 验证
    try:
        common = os.path.commonpath([abs_path, abs_allowed])
        if common != abs_allowed:
            logger.warning(f"路径遍历尝试: {file_path}")
            return None
    except ValueError:
        # 不同驱动器（Windows）
        logger.warning(f"无效路径: {file_path}")
        return None

    return abs_path


def is_safe_filename(filename):
    """
    检查文件名是否安全（不包含路径遍历字符）

    Args:
        filename: 要检查的文件名

    Returns:
        bool: 是否安全
    """
    unsafe_patterns = ['..', '/', '\\']
    return not any(pattern in filename for pattern in unsafe_patterns)


# Code processing functions
def clean_code(code: str) -> str:
    """
    清理代码中的转义字符
    处理 PowerShell 等发送的转义换行符
    注意：只在字符串外部处理转义，保留字符串内部的转义序列

    Args:
        code: 原始代码字符串

    Returns:
        清理后的代码字符串
    """
    # 简单清理实现
    result = []
    i = 0
    length = len(code)
    in_string = False

    while i < length:
        char = code[i]

        # 处理字符串边界
        if char == '"':
            if i > 0 and code[i - 1] == '\\':
                result.append(char)
                i += 1
            else:
                in_string = not in_string
                result.append(char)
                i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        # 处理转义字符
        if char == '`' and i + 1 < length and code[i + 1] == 'n':
            result.append('\n')
            i += 2
        elif char == '\\' and i + 1 < length and code[i + 1] == 'n':
            result.append('\n')
            i += 2
        elif char == '\\' and i + 1 < length and code[i + 1] == 't':
            result.append('\t')
            i += 2
        elif char == '\\' and i + 1 < length and code[i + 1] == '"':
            result.append(char)
            result.append(code[i + 1])
            i += 2
        else:
            result.append(char)
            i += 1

    return ''.join(result)


def extract_includes(code: str) -> List[str]:
    """
    从 HPL 代码中提取 includes 列表
    使用正则表达式解析，避免 YAML 解析错误

    Args:
        code: HPL代码字符串

    Returns:
        list: include文件列表
    """
    includes = []
    try:
        includes_pattern = r'^includes:\s*(?:\r?\n)((?:\s*-\s*.+\s*(?:\r?\n)?)*)'
        match = re.search(includes_pattern, code, re.MULTILINE)

        if match:
            list_content = match.group(1)
            item_pattern = r'^\s*-\s*(.+?)\s*$'
            for line in list_content.split('\n'):
                item_match = re.match(item_pattern, line)
                if item_match:
                    include_file = item_match.group(1).strip()
                    include_file = include_file.strip('"\'')
                    includes.append(include_file)
    except Exception:
        pass
    return includes


def copy_include_files(code: str, temp_dir: str,
                       base_dir: Optional[str] = None,
                       current_file: Optional[str] = None,
                       original_file: Optional[str] = None) -> Tuple[List[str], str, List[str]]:
    """
    复制 include 文件到临时目录
    从多个可能的目录查找 include 文件

    Args:
        code: HPL代码
        temp_dir: 临时目录路径
        base_dir: 基础搜索目录（可选）
        current_file: 当前执行的HPL文件路径（可选）
        original_file: 原始文件路径

    Returns:
        tuple: (copied_files列表, 更新后的代码, 未找到的includes列表)
    """
    includes = extract_includes(code)
    if not includes:
        return [], code, []

    copied_files = []
    not_found = []

    # 确定有效的当前文件目录
    effective_file = original_file if original_file else current_file
    current_dir = None

    if effective_file:
        current_dir = os.path.dirname(os.path.abspath(effective_file))

    # 定义搜索路径
    search_paths = []

    if current_dir and os.path.exists(current_dir):
        search_paths.append(current_dir)

    if base_dir and os.path.exists(base_dir):
        search_paths.append(os.path.abspath(base_dir))

    # 项目根目录
    project_root = os.path.join(os.path.dirname(__file__), '..', '..')
    search_paths.append(os.path.abspath(project_root))

    # examples 目录
    examples_dir = os.path.join(project_root, 'examples')
    if os.path.exists(examples_dir):
        search_paths.append(examples_dir)

    for include_file in includes:
        resolved_path = None

        if include_file.startswith('./') or include_file.startswith('../'):
            if current_dir:
                try:
                    resolved_path = os.path.normpath(os.path.join(current_dir, include_file))
                    if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                        pass
                    else:
                        resolved_path = None
                except Exception:
                    resolved_path = None

        clean_include = os.path.normpath(include_file).lstrip('/\\')
        if '..' in clean_include:
            logger.warning(f"跳过非法 include 路径: {include_file}")
            not_found.append(include_file)
            continue

        found = False

        if resolved_path and os.path.exists(resolved_path):
            source_path = resolved_path
            if include_file.startswith('./') or include_file.startswith('../'):
                dest_path = os.path.join(temp_dir, clean_include)
            else:
                dest_path = os.path.join(temp_dir, os.path.basename(clean_include))

            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except Exception:
                    not_found.append(include_file)
                    continue

            try:
                shutil.copy2(source_path, dest_path)
                copied_files.append(dest_path)
                found = True
            except Exception:
                pass

        if not found:
            for search_dir in search_paths:
                source_path = os.path.join(search_dir, clean_include)
                if os.path.exists(source_path) and os.path.isfile(source_path):
                    dest_path = os.path.join(temp_dir, clean_include)

                    dest_dir = os.path.dirname(dest_path)
                    if dest_dir and not os.path.exists(dest_dir):
                        try:
                            os.makedirs(dest_dir, exist_ok=True)
                        except Exception:
                            continue

                    try:
                        shutil.copy2(source_path, dest_path)
                        copied_files.append(dest_path)
                        found = True
                        break
                    except Exception:
                        continue

        if not found:
            not_found.append(include_file)

    return copied_files, code, not_found
