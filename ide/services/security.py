"""
安全服务模块
提供请求限制和路径验证功能
"""

import os
import logging
from functools import wraps
from flask import request, jsonify

from config import MAX_REQUEST_SIZE, ALLOWED_EXAMPLES_DIR


logger = logging.getLogger(__name__)


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
