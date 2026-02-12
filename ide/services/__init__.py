"""
IDE Services 包
提供简化的 HPL 语言验证、执行和代码处理功能
"""

# 执行服务
from ide.services.execution_service import (
    HPLEngine,
    SandboxExecutor,
    HPLExecutionService,
    get_execution_service
)

# 代码服务
from ide.services.code_service import (
    limit_request_size,
    validate_path,
    is_safe_filename,
    clean_code,
    extract_includes,
    copy_include_files
)


# 运行时管理
from ide.services.runtime_manager import (
    check_runtime_available,
    get_runtime_info,
    is_runtime_available
)

__all__ = [
    # 执行服务
    'HPLEngine',
    'SandboxExecutor',
    'HPLExecutionService',
    'get_execution_service',

    # 代码服务
    'limit_request_size',
    'validate_path',
    'is_safe_filename',
    'clean_code',
    'extract_includes',
    'copy_include_files',


    # 运行时管理
    'check_runtime_available',
    'get_runtime_info',
    'is_runtime_available',
]

# 包版本
__version__ = '1.0.0'
