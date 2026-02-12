"""
路由模块
"""
from flask import Flask

from .static import register_static_routes
from .execution_routes import register_execution_routes
from .file_routes import register_file_routes
from .example_routes import register_example_routes
from .health_routes import register_health_routes


def register_all_routes(app: Flask):
    """
    注册所有路由

    Args:
        app: Flask应用实例
    """
    register_static_routes(app)
    register_execution_routes(app)
    register_file_routes(app)
    register_example_routes(app)
    register_health_routes(app)
