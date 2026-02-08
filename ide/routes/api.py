"""
API路由模块
提供所有REST API端点
"""

import os
import shutil
import tempfile
import logging
from flask import Flask, request, jsonify

from config import (
    MAX_REQUEST_SIZE, MAX_EXECUTION_TIME, 
    ALLOWED_EXAMPLES_DIR, SERVER_VERSION
)
from utils.helpers import execute_with_timeout, TimeoutException
from services.security import limit_request_size, validate_path, is_safe_filename
from services.code_processor import clean_code, copy_include_files
from services.code_executor import execute_hpl, check_runtime_available


logger = logging.getLogger(__name__)


def register_api_routes(app: Flask):
    """
    注册API路由
    
    Args:
        app: Flask应用实例
    """
    
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
        if not check_runtime_available():
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
                    shutil.rmtree(temp_dir)
                    logger.info(f"清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.error(f"清理临时目录失败: {temp_dir}, 错误: {e}")

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
                        if not is_safe_filename(filename):
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
        if not is_safe_filename(filename):
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
            'version': SERVER_VERSION,
            'max_execution_time': MAX_EXECUTION_TIME,
            'max_request_size': MAX_REQUEST_SIZE
        })
