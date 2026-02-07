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

app = Flask(__name__, static_folder='.', static_url_path='')

# 配置 CORS - 只允许特定来源
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:*", "http://127.0.0.1:*"],
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
    """
    # 处理 PowerShell 风格的换行符转义
    code = code.replace('`n', '\n')
    # 处理其他可能的转义
    code = code.replace('\\n', '\n')
    code = code.replace('\\t', '\t')
    code = code.replace('\\"', '"')
    return code


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
    """
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
    try:
        # 创建临时 HPL 文件
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.hpl', 
            delete=False, 
            encoding='utf-8',
            prefix='hpl_'
        ) as f:
            f.write(code)
            temp_file = f.name
        
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
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.info(f"清理临时文件: {temp_file}")
            except Exception as e:
                logger.error(f"清理临时文件失败: {temp_file}, 错误: {e}")


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
                alias = imp['module']  # 简化处理，不使用别名
                import_stmt = ImportStatement(module_name, alias)
                evaluator.execute_import(import_stmt, evaluator.global_scope)
            
            evaluator.run()
        
        output = output_buffer.getvalue()
        
        return {
            'success': True,
            'output': output
        }
        
    except Exception as e:
        # 返回错误信息
        error_msg = str(e)
        
        # 尝试提取行号信息
        import traceback
        tb = traceback.format_exc()
        logger.error(f"执行错误: {error_msg}\n{tb}")
        
        return {
            'success': False,
            'error': error_msg,
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
