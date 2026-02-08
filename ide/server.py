#!/usr/bin/env python3
"""
HPL IDE 后端服务器
提供 HPL 代码执行 API

安全特性：
- 执行超时限制（默认5秒）
- 请求大小限制（最大1MB）
- 路径遍历防护
- 临时文件自动清理
"""

import sys

import os
import tempfile
import signal
import threading
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加 hpl_runtime 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 检查 hpl-runtime 是否已安装（延迟检查，允许静态文件服务）
hpl_runtime_available = False
try:
    import hpl_runtime
    hpl_runtime_available = True
    logger.info("hpl-runtime 已加载")
except ImportError:
    logger.warning("hpl-runtime 未安装。代码执行功能将不可用。请运行: pip install hpl-runtime")



app = Flask(__name__, static_folder='.', static_url_path='')

# 配置 CORS - 只允许特定来源（生产环境应限制具体端口）
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5000", "http://127.0.0.1:5000", 
                   "http://localhost:3000", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})


# 安全配置
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB
MAX_EXECUTION_TIME = 5  # 5秒
ALLOWED_EXAMPLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'examples')
)


def limit_request_size(max_size):
    """装饰器：限制请求大小"""
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


class TimeoutException(Exception):
    """执行超时异常"""
    pass


def timeout_handler(signum, frame):
    """信号处理函数：执行超时"""
    raise TimeoutException("代码执行超时")


def execute_with_timeout(func, timeout_sec, *args, **kwargs):
    """
    带超时的函数执行
    使用线程实现跨平台兼容
    """
    result = [None]
    exception = [None]
    
    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_sec)
    
    if thread.is_alive():
        logger.warning(f"代码执行超时（{timeout_sec}秒）")
        raise TimeoutException(f"代码执行超过 {timeout_sec} 秒限制")
    
    if exception[0]:
        raise exception[0]
    
    return result[0]


def clean_code(code):
    """
    清理代码中的转义字符
    处理 PowerShell 等发送的转义换行符
    注意：只在字符串外部处理转义，保留字符串内部的转义序列
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
    """
    includes = []
    try:
        # 使用正则表达式匹配 includes 部分
        # 匹配 includes: 后面跟着的列表项
        import re
        
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
    返回: (copied_files列表, 更新后的代码, 未找到的includes列表)
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
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    search_paths.append(project_root)
    
    # 3. examples 目录
    examples_dir = os.path.join(project_root, 'examples')
    if os.path.exists(examples_dir):
        search_paths.append(examples_dir)
    
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
                    import shutil
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




def validate_path(file_path, allowed_dir):
    """
    验证文件路径是否在允许的目录内
    防止路径遍历攻击
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


@app.route('/api/run', methods=['POST'])
@limit_request_size(MAX_REQUEST_SIZE)
def run_code():
    """
    执行 HPL 代码
    接收代码字符串，保存到临时文件并执行
    添加超时限制防止无限循环
    自动处理 include 文件复制
    """
    # 检查 hpl_runtime 是否可用
    if not hpl_runtime_available:
        return jsonify({
            'success': False,
            'error': 'hpl-runtime 未安装，无法执行代码',
            'hint': '请运行: pip install hpl-runtime'
        }), 503
    
    code = request.form.get('code', '')
    
    if not code.strip():
        return jsonify({
            'success': False,
            'error': '代码为空'
        })

    
    # 清理代码中的转义字符
    code = clean_code(code)
    
    # 创建临时文件
    temp_file = None
    temp_include_files = []
    temp_dir = None
    try:
        # 创建临时目录（用于存放 include 文件）
        temp_dir = tempfile.mkdtemp(prefix='hpl_')
        
        # 复制 include 文件到临时目录
        temp_include_files, code, not_found_includes = copy_include_files(code, temp_dir)
        
        # 如果有未找到的 include 文件，记录警告
        if not_found_includes:
            logger.warning(f"未找到的 include 文件: {', '.join(not_found_includes)}")

        
        # 创建临时 HPL 文件（在临时目录中，以便正确解析 includes）
        temp_file = os.path.join(temp_dir, 'main.hpl')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        logger.info(f"执行临时文件: {temp_file}")
        
        # 执行 HPL 代码（带超时）
        result = execute_with_timeout(execute_hpl, MAX_EXECUTION_TIME, temp_file)
        return jsonify(result)
        
    except TimeoutException as e:
        logger.warning(f"执行超时: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'执行超时: 代码运行超过 {MAX_EXECUTION_TIME} 秒限制'
        })
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        })
    finally:
        # 清理临时目录及所有文件
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.info(f"清理临时目录: {temp_dir}")
            except Exception as e:
                logger.error(f"清理临时目录失败: {temp_dir}, 错误: {e}")



def execute_hpl(file_path):
    """
    执行 HPL 文件
    使用 hpl_runtime 执行代码
    在受限环境中运行
    """
    try:
        # 方法1: 直接导入执行
        from hpl_runtime.parser import HPLParser
        from hpl_runtime.evaluator import HPLEvaluator
        from hpl_runtime.models import ImportStatement

        import io
        import contextlib
        
        # 捕获输出
        output_buffer = io.StringIO()
        
        with contextlib.redirect_stdout(output_buffer):
            parser = HPLParser(file_path)
            classes, objects, main_func, call_target, imports = parser.parse()
            
            evaluator = HPLEvaluator(classes, objects, main_func, call_target)
            
            # 处理顶层导入
            for imp in imports:
                module_name = imp['module']
                alias = imp.get('alias', module_name)
                # 使用ImportStatement 类
                
                import_stmt = ImportStatement(module_name, alias)
                evaluator.execute_import(import_stmt, evaluator.global_scope)

            
            evaluator.run()
        
        output = output_buffer.getvalue()
        
        return {
            'success': True,
            'output': output
        }
        
    except ImportError as e:
        # hpl_runtime 导入错误
        error_msg = f"hpl-runtime 导入错误: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'hint': '请确保已安装 hpl-runtime: pip install hpl-runtime'
        }

    except SyntaxError as e:
        # HPL 代码语法错误
        error_msg = f"HPL 语法错误 (行 {e.lineno}, 列 {e.offset or 1}): {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'line': e.lineno,
            'column': e.offset or 1,
            'type': 'syntax_error',
            'text': e.text
        }

    except Exception as e:
        # 其他错误
        error_msg = str(e)
        
        # 尝试提取行号信息
        import traceback
        tb = traceback.format_exc()
        logger.error(f"执行错误: {error_msg}\n{tb}")
        
        # 尝试从 traceback 中提取行号
        line_no = None
        try:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_tb:
                last_frame = traceback.extract_tb(exc_tb)[-1]
                line_no = last_frame.lineno
        except Exception:
            pass
        
        return {
            'success': False,
            'error': error_msg,
            'line': line_no,
            'traceback': tb
        }




@app.route('/api/examples', methods=['GET'])
def list_examples():
    """
    列出可用的示例文件
    """
    examples = []
    
    try:
        if os.path.exists(ALLOWED_EXAMPLES_DIR):
            for filename in sorted(os.listdir(ALLOWED_EXAMPLES_DIR)):
                if filename.endswith('.hpl'):
                    # 验证文件名（防止路径遍历）
                    if '..' in filename or '/' in filename or '\\' in filename:
                        continue
                    
                    file_path = os.path.join(ALLOWED_EXAMPLES_DIR, filename)
                    # 验证路径
                    validated_path = validate_path(file_path, ALLOWED_EXAMPLES_DIR)
                    if validated_path and os.path.isfile(validated_path):
                        examples.append({
                            'name': filename,
                            'path': f'examples/{filename}',
                            'size': os.path.getsize(validated_path)
                        })
    except Exception as e:
        logger.error(f"列出示例文件错误: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
    return jsonify({
        'success': True,
        'examples': examples
    })


@app.route('/api/examples/<path:filename>', methods=['GET'])
def get_example(filename):
    """
    获取示例文件内容
    严格验证路径防止目录遍历
    """
    # 安全检查：防止目录遍历
    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        logger.warning(f"非法文件名尝试: {filename}")
        return jsonify({
            'success': False,
            'error': '无效的文件名'
        })
    
    # 构建完整路径并验证
    file_path = os.path.join(ALLOWED_EXAMPLES_DIR, filename)
    validated_path = validate_path(file_path, ALLOWED_EXAMPLES_DIR)
    
    if not validated_path:
        return jsonify({
            'success': False,
            'error': '无效的文件路径'
        })
    
    try:
        if os.path.exists(validated_path) and os.path.isfile(validated_path):
            with open(validated_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"读取示例文件: {validated_path}")
            return jsonify({
                'success': True,
                'content': content,
                'name': filename
            })
        else:
            return jsonify({
                'success': False,
                'error': '文件不存在'
            })
    except Exception as e:
        logger.error(f"读取示例文件错误: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    健康检查端点
    """
    return jsonify({
        'status': 'ok',
        'message': 'HPL IDE Server is running',
        'version': '1.1.0',
        'max_execution_time': MAX_EXECUTION_TIME,
        'max_request_size': MAX_REQUEST_SIZE
    })


@app.route('/', methods=['GET'])
def serve_index():
    """
    提供 IDE 主页面
    """
    return app.send_static_file('index.html')


@app.route('/js/<path:filename>', methods=['GET'])
def serve_js(filename):
    """
    提供 JavaScript 文件
    """
    return app.send_static_file(f'js/{filename}')


@app.route('/css/<path:filename>', methods=['GET'])
def serve_css(filename):
    """
    提供 CSS 文件
    """
    return app.send_static_file(f'css/{filename}')


def main():
    print("=" * 60)
    print("HPL IDE Server v1.1.0")
    print("=" * 60)
    print("安全特性:")
    print(f"  - 执行超时: {MAX_EXECUTION_TIME} 秒")
    print(f"  - 请求大小限制: {MAX_REQUEST_SIZE} bytes")
    print("  - 路径遍历防护: 已启用")
    print("  - CORS 限制: 已启用")
    print("-" * 60)
    print("功能状态:")
    print(f"  - 代码执行: {'可用' if hpl_runtime_available else '不可用 (未安装 hpl-runtime)'}")
    print(f"  - 静态文件服务: 可用")
    print(f"  - 示例文件服务: 可用")
    print("-" * 60)
    print("API 端点:")
    print("  POST /api/run           - 执行 HPL 代码")
    print("  GET  /api/examples      - 列出示例文件")
    print("  GET  /api/examples/<name> - 获取示例内容")
    print("  GET  /api/health        - 健康检查")
    print("=" * 60)
    print("服务器运行在 http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    # 确保示例目录存在
    if not os.path.exists(ALLOWED_EXAMPLES_DIR):
        logger.warning(f"示例目录不存在: {ALLOWED_EXAMPLES_DIR}")
    
    app.run(host='0.0.0.0', port=5000, debug=False)



if __name__ == '__main__':
    main()
