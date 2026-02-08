"""
静态文件服务路由
提供IDE前端静态资源
"""

import os
import logging
from flask import Flask, send_from_directory

from config import BASE_DIR


logger = logging.getLogger(__name__)


def register_static_routes(app: Flask):
    """
    注册静态文件路由
    
    Args:
        app: Flask应用实例
    """
    
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
