"""
示例文件路由
处理示例文件的浏览和获取
"""

import os
import logging
from flask import request, jsonify

from ide.services.code_service import validate_path, is_safe_filename
from config import ALLOWED_EXAMPLES_DIR

logger = logging.getLogger(__name__)


def register_example_routes(app):
    """
    注册示例文件路由

    Args:
        app: Flask应用实例
    """

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
                        if not is_safe_filename(filename):
                            continue

                        file_path = os.path.join(ALLOWED_EXAMPLES_DIR, filename)
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
        """
        if not is_safe_filename(filename):
            logger.warning(f"非法文件名尝试: {filename}")
            return jsonify({
                'success': False,
                'error': '无效的文件名'
            })

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
