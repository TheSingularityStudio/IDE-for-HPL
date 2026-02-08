"""
HPL IDE 服务器配置
集中管理所有配置常量
"""

import os

# 安全配置
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB
MAX_EXECUTION_TIME = 5  # 5秒

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
ALLOWED_EXAMPLES_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, 'workspace'))  # 改为workspace目录

# CORS配置
CORS_ORIGINS = [
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

CORS_METHODS = ["GET", "POST"]
CORS_HEADERS = ["Content-Type"]

# 服务器配置
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_VERSION = '1.1.0'

# 日志配置
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'
