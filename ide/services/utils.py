"""
工具模块
提供共享的工具函数和配置
"""

import os
import sys
import logging
import tempfile
from typing import Optional

# 配置日志
logger = logging.getLogger(__name__)

# 项目路径配置
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ALLOWED_EXAMPLES_DIR = os.path.join(PROJECT_ROOT, 'examples')

# 运行时可用性缓存
_hpl_runtime_available = None


def check_runtime_available() -> bool:
    """
    检查 hpl_runtime 是否可用
    
    Returns:
        bool: 是否可用
    """
    global _hpl_runtime_available
    
    if _hpl_runtime_available is None:
        try:
            import hpl_runtime
            _hpl_runtime_available = True
            logger.info("hpl-runtime 已加载")
        except ImportError:
            _hpl_runtime_available = False
            logger.warning("hpl-runtime 未安装")
    
    return _hpl_runtime_available


def setup_module_path():
    """
    设置模块搜索路径
    添加 examples 目录到 sys.path
    """
    if ALLOWED_EXAMPLES_DIR not in sys.path:
        sys.path.insert(0, ALLOWED_EXAMPLES_DIR)
        logger.debug(f"添加模块路径: {ALLOWED_EXAMPLES_DIR}")


def create_temp_file(code: str, suffix: str = '.hpl') -> str:
    """
    创建临时文件
    
    Args:
        code: 文件内容
        suffix: 文件后缀
    
    Returns:
        str: 临时文件路径
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix,
                                     delete=False, encoding='utf-8') as f:
        f.write(code)
        return f.name


def cleanup_temp_file(file_path: str):
    """
    清理临时文件
    
    Args:
        file_path: 临时文件路径
    """
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.debug(f"清理临时文件失败: {e}")


def get_code_at_line(code: str, line_num: int) -> Optional[str]:
    """
    获取指定行的代码
    
    Args:
        code: 源代码
        line_num: 行号（1-based）
    
    Returns:
        str: 该行代码，如果行号无效则返回 None
    """
    if not code or line_num < 1:
        return None
    
    lines = code.split('\n')
    if line_num <= len(lines):
        return lines[line_num - 1]
    return None


def get_surrounding_lines(code: str, line_num: int, 
                         context_lines: int = 3) -> list:
    """
    获取指定行周围的代码
    
    Args:
        code: 源代码
        line_num: 行号（1-based）
        context_lines: 上下文行数
    
    Returns:
        list: 周围行信息列表
    """
    if not code or line_num < 1:
        return []
    
    lines = code.split('\n')
    start = max(0, line_num - context_lines - 1)
    end = min(len(lines), line_num + context_lines)
    
    surrounding = []
    for i in range(start, end):
        surrounding.append({
            'line_number': i + 1,
            'content': lines[i],
            'is_error_line': (i + 1) == line_num
        })
    
    return surrounding


def format_error_message(error: Exception, source_code: str = None) -> str:
    """
    格式化错误消息
    
    Args:
        error: 异常对象
        source_code: 源代码（可选）
    
    Returns:
        str: 格式化后的错误消息
    """
    try:
        from hpl_runtime import format_error_for_user
        return format_error_for_user(error, source_code)
    except ImportError:
        # 基础错误格式化
        msg = str(error)
        if hasattr(error, 'line') and error.line:
            msg = f"行 {error.line}: {msg}"
        return msg


def validate_path(file_path: str, allowed_dir: str) -> Optional[str]:
    """
    验证文件路径是否在允许的目录内
    防止路径遍历攻击
    
    Args:
        file_path: 要验证的文件路径
        allowed_dir: 允许的根目录
    
    Returns:
        str: 验证通过的绝对路径，或 None（如果验证失败）
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


def is_safe_filename(filename: str) -> bool:
    """
    检查文件名是否安全（不包含路径遍历字符）
    
    Args:
        filename: 要检查的文件名
    
    Returns:
        bool: 是否安全
    """
    unsafe_patterns = ['..', '/', '\\']
    return not any(pattern in filename for pattern in unsafe_patterns)
