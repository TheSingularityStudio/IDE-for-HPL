"""
执行相关路由
处理代码运行、验证和调试的API端点
"""

import logging
from flask import request, jsonify

from ide.services.execution_service import get_execution_service
from ide.services.code_service import limit_request_size, validate_code
from config import MAX_REQUEST_SIZE

logger = logging.getLogger(__name__)


def register_execution_routes(app):
    """
    注册执行相关路由

    Args:
        app: Flask应用实例
    """

    @app.route('/api/run', methods=['POST'])
    @limit_request_size(MAX_REQUEST_SIZE)
    def run_code():
        """
        执行 HPL 代码
        """
        service = get_execution_service()

        code = request.form.get('code', '')
        input_data = request.form.get('input_data', None)
        if input_data:
            try:
                input_data = json.loads(input_data)
            except:
                pass

        if not code.strip():
            return jsonify({'success': False, 'error': '代码为空'})

        result = service.execute_code(code, input_data=input_data)
        return jsonify(result)

    @app.route('/api/validate', methods=['POST'])
    @limit_request_size(MAX_REQUEST_SIZE)
    def validate_syntax():
        """
        语法验证端点
        """
        code = request.form.get('code', '')

        if not code.strip():
            return jsonify({
                'success': True,
                'valid': True,
                'errors': [],
                'warnings': [],
                'message': '代码为空'
            })

        try:
            diagnostics = validate_code_syntax(code)
            return jsonify({
                'success': True,
                'valid': len([d for d in diagnostics if d.get('severity') == 'error']) == 0,
                'errors': [d for d in diagnostics if d.get('severity') == 'error'],
                'warnings': [d for d in diagnostics if d.get('severity') == 'warning']
            })

        except Exception as e:
            logger.error(f"语法验证失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'语法验证失败: {str(e)}',
                'valid': False,
                'errors': [],
                'warnings': []
            }), 500
