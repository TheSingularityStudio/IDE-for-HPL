"""
路由模块
"""
from flask import Flask

from .static import register_static_routes
from .api import register_api_routes


def register_all_routes(app: Flask):
    """
    注册所有路由
    
    Args:
        app: Flask应用实例
    """
    register_static_routes(app)
    register_api_routes(app)
