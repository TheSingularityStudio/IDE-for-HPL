#!/usr/bin/env python3
"""
HPL IDE 后端服务器
提供 HPL 代码执行 API

安全特性：
- 执行超时限制（默认5秒）
- 请求大小限制（最大1MB）
- 路径遍历防护
- 临时文件自动清理

模块结构：
- config.py: 配置常量
- routes/: 路由处理
- services/: 业务逻辑
- utils/: 通用工具
"""

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask
from flask_cors import CORS

from config import (
    LOG_FORMAT, LOG_LEVEL, CORS_ORIGINS, CORS_METHODS, CORS_HEADERS,
    SERVER_HOST, SERVER_PORT, SERVER_VERSION,
    MAX_REQUEST_SIZE, MAX_EXECUTION_TIME, ALLOWED_EXAMPLES_DIR
)
from routes import register_all_routes
from services.code_executor import check_runtime_available

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__, static_folder='.', static_url_path='')

# 配置 CORS
CORS(app, resources={
    r"/api/*": {
        "origins": CORS_ORIGINS,
        "methods": CORS_METHODS,
        "allow_headers": CORS_HEADERS
    }
})

# 注册所有路由
register_all_routes(app)


def main():
    """服务器主入口"""
    hpl_available = check_runtime_available()
    
    print("=" * 60)
    print(f"HPL IDE Server v{SERVER_VERSION}")
    print("=" * 60)
    print("安全特性:")
    print(f"  - 执行超时: {MAX_EXECUTION_TIME} 秒")
    print(f"  - 请求大小限制: {MAX_REQUEST_SIZE} bytes")
    print("  - 路径遍历防护: 已启用")
    print("  - CORS 限制: 已启用")
    print("-" * 60)
    print("功能状态:")
    print(f"  - 代码执行: {'可用' if hpl_available else '不可用 (未安装 hpl-runtime)'}")
    print(f"  - 静态文件服务: 可用")
    print(f"  - 示例文件服务: 可用")
    print("-" * 60)
    print("API 端点:")
    print("  POST /api/run           - 执行 HPL 代码")
    print("  GET  /api/examples      - 列出示例文件")
    print("  GET  /api/examples/<name> - 获取示例内容")
    print("  GET  /api/health        - 健康检查")
    print("=" * 60)
    print(f"服务器运行在 http://localhost:{SERVER_PORT}")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    # 确保示例目录存在
    if not os.path.exists(ALLOWED_EXAMPLES_DIR):
        logger.warning(f"示例目录不存在: {ALLOWED_EXAMPLES_DIR}")
    
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)


if __name__ == '__main__':
    main()
