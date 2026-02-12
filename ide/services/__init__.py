"""
IDE Services 包
提供 HPL 语言的验证、执行、调试和代码处理功能
"""

# 核心引擎
from ide.services.hpl_engine import (
    HPLEngine,
    Diagnostic,
    ParseCache,
    validate_code,
    get_completions,
    execute_code,
    debug_code,
    get_code_outline,
    check_runtime_available
)

# 调试服务
from ide.services.debug_service import (
    HPLDebugService,
    ErrorAnalyzer,
    Breakpoint,
    ExecutionTraceEntry,
    get_debug_service,
    get_error_analyzer,
    debug_file,
    debug_code as debug_service_code,
    analyze_error
)

# 语法验证
from ide.services.syntax_validator import (
    HPLSyntaxValidator,
    SyntaxErrorInfo,
    get_validator,
    validate_code as validator_validate_code,
    validate_with_suggestions,
    get_error_details
)

# 代码执行
from ide.services.code_executor import (
    execute_hpl,
    execute_hpl_code,
    execute_with_debug,
    get_execution_trace,
    get_variable_snapshots,
    analyze_execution_error,
    run_hpl,
    run_hpl_code
)

# 代码处理
from ide.services.code_processor import (
    clean_code,
    extract_includes,
    copy_include_files,
    process_for_debug,
    get_error_context,
    get_completion_items,
    get_code_outline as processor_get_code_outline,
    get_completions
)

# 工具函数
from ide.services.utils import (
    setup_module_path,
    create_temp_file,
    cleanup_temp_file,
    get_code_at_line,
    get_surrounding_lines,
    format_error_message,
    validate_path,
    is_safe_filename,
    PROJECT_ROOT,
    ALLOWED_EXAMPLES_DIR
)

__all__ = [
    # 核心引擎
    'HPLEngine',
    'Diagnostic',
    'ParseCache',
    'validate_code',
    'get_completions',
    'execute_code',
    'debug_code',
    'get_code_outline',
    'check_runtime_available',
    
    # 调试服务
    'HPLDebugService',
    'ErrorAnalyzer',
    'Breakpoint',
    'ExecutionTraceEntry',
    'get_debug_service',
    'get_error_analyzer',
    'debug_file',
    'analyze_error',
    
    # 语法验证
    'HPLSyntaxValidator',
    'SyntaxErrorInfo',
    'get_validator',
    'validate_with_suggestions',
    'get_error_details',
    
    # 代码执行
    'execute_hpl',
    'execute_hpl_code',
    'execute_with_debug',
    'get_execution_trace',
    'get_variable_snapshots',
    'analyze_execution_error',
    'run_hpl',
    'run_hpl_code',
    
    # 代码处理
    'clean_code',
    'extract_includes',
    'copy_include_files',
    'process_for_debug',
    'get_error_context',
    'get_completion_items',
    'get_completions',
    
    # 工具函数
    'setup_module_path',
    'create_temp_file',
    'cleanup_temp_file',
    'get_code_at_line',
    'get_surrounding_lines',
    'format_error_message',
    'validate_path',
    'is_safe_filename',
    'PROJECT_ROOT',
    'ALLOWED_EXAMPLES_DIR',
]

# 包版本
__version__ = '2.0.0'
