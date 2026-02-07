"""
HPL IDE 后端服务器
提供 HPL 代码执行 API
"""

import sys
import os
import tempfile
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS

# 添加 hpl_runtime 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # 启用跨域支持



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


@app.route('/run', methods=['POST'])
def run_code():
    """
    执行 HPL 代码
    接收代码字符串，保存到临时文件并执行
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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.hpl', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        # 执行 HPL 代码
        result = execute_hpl(temp_file)
        return jsonify(result)

        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        })
    finally:
        # 清理临时文件
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


def execute_hpl(file_path):
    """
    执行 HPL 文件
    使用 hpl_runtime 执行代码
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
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': tb
        }


@app.route('/examples', methods=['GET'])
def list_examples():
    """
    列出可用的示例文件
    """
    examples_dir = os.path.join(os.path.dirname(__file__), '..', 'examples')
    examples = []
    
    try:
        if os.path.exists(examples_dir):
            for filename in sorted(os.listdir(examples_dir)):
                if filename.endswith('.hpl'):
                    file_path = os.path.join(examples_dir, filename)
                    examples.append({
                        'name': filename,
                        'path': f'examples/{filename}',
                        'size': os.path.getsize(file_path)
                    })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
    return jsonify({
        'success': True,
        'examples': examples
    })


@app.route('/examples/<path:filename>', methods=['GET'])
def get_example(filename):
    """
    获取示例文件内容
    """
    # 安全检查：防止目录遍历
    if '..' in filename or filename.startswith('/'):
        return jsonify({
            'success': False,
            'error': '无效的文件名'
        })
    
    file_path = os.path.join(os.path.dirname(__file__), '..', 'examples', filename)
    
    try:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
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
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/health', methods=['GET'])
def health_check():
    """
    健康检查端点
    """
    return jsonify({
        'status': 'ok',
        'message': 'HPL IDE Server is running'
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
    print("=" * 50)
    print("HPL IDE Server")
    print("=" * 50)
    print("API 端点:")
    print("  POST /run     - 执行 HPL 代码")
    print("  GET  /examples       - 列出示例文件")
    print("  GET  /examples/<name> - 获取示例内容")
    print("  GET  /health         - 健康检查")
    print("=" * 50)
    print("服务器运行在 http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    main()
