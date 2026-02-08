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
    ALLOWED_WORKSPACE_DIR, ALLOWED_EXAMPLES_DIR, SERVER_VERSION
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

    def get_base_path(mode):
        """
        根据模式获取基础路径
        """
        if mode == 'workspace':
            return ALLOWED_WORKSPACE_DIR
        return ALLOWED_EXAMPLES_DIR

    @app.route('/api/files/tree', methods=['GET'])
    def get_file_tree():
        """
        获取文件树结构
        递归扫描 workspace 或 examples 目录
        """
        mode = request.args.get('mode', 'workspace')
        base_path = get_base_path(mode)
        
        def build_tree(path, base_path):
            """
            递归构建文件树
            """
            try:
                rel_path = os.path.relpath(path, base_path)
                name = os.path.basename(path)
                
                if os.path.isdir(path):
                    children = []
                    try:
                        for item in sorted(os.listdir(path)):
                            # 跳过隐藏文件和 __pycache__
                            if item.startswith('.') or item == '__pycache__':
                                continue
                            
                            item_path = os.path.join(path, item)
                            validated = validate_path(item_path, base_path)
                            if validated:
                                child_node = build_tree(validated, base_path)
                                if child_node:
                                    children.append(child_node)
                    except (OSError, PermissionError) as e:
                        logger.warning(f"无法读取目录 {path}: {e}")
                    
                    return {
                        'name': name,
                        'path': rel_path.replace('\\', '/'),
                        'type': 'folder',
                        'children': children
                    }
                else:
                    # 文件节点
                    return {
                        'name': name,
                        'path': rel_path.replace('\\', '/'),
                        'type': 'file',
                        'size': os.path.getsize(path)
                    }
            except Exception as e:
                logger.error(f"构建文件树错误 {path}: {e}")
                return None
        
        try:
            if not os.path.exists(base_path):
                return jsonify({
                    'success': False,
                    'error': f'{"工作区" if mode == "workspace" else "示例"}目录不存在'
                })
            
            tree = build_tree(base_path, base_path)
            
            return jsonify({
                'success': True,
                'tree': tree
            })
        except Exception as e:
            logger.error(f"获取文件树错误: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/files/create', methods=['POST'])
    def create_file():
        """
        创建新文件
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': '请求数据不能为空'
                })
            
            path = data.get('path', '')
            content = data.get('content', '')
            mode = data.get('mode', 'workspace')
            
            if not path:
                return jsonify({
                    'success': False,
                    'error': '文件路径不能为空'
                })
            
            # 安全检查
            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的文件名'
                })
            
            # 根据模式选择基础路径
            base_path = get_base_path(mode)
            
            # 构建完整路径并验证
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)
            
            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件路径'
                })
            
            # 检查文件是否已存在
            if os.path.exists(validated_path):
                return jsonify({
                    'success': False,
                    'error': '文件已存在'
                })
            
            # 确保父目录存在
            parent_dir = os.path.dirname(validated_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            # 创建文件
            with open(validated_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"创建文件: {validated_path}")
            return jsonify({
                'success': True,
                'message': '文件创建成功',
                'path': path
            })
            
        except Exception as e:
            logger.error(f"创建文件错误: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/folders/create', methods=['POST'])
    def create_folder():
        """
        创建新文件夹
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': '请求数据不能为空'
                })
            
            path = data.get('path', '')
            mode = data.get('mode', 'workspace')
            
            if not path:
                return jsonify({
                    'success': False,
                    'error': '文件夹路径不能为空'
                })
            
            # 安全检查
            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的文件夹名'
                })
            
            # 根据模式选择基础路径
            base_path = get_base_path(mode)
            
            # 构建完整路径并验证
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)
            
            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件夹路径'
                })
            
            # 检查是否已存在
            if os.path.exists(validated_path):
                return jsonify({
                    'success': False,
                    'error': '文件夹已存在'
                })
            
            # 创建文件夹
            os.makedirs(validated_path, exist_ok=True)
            
            logger.info(f"创建文件夹: {validated_path}")
            return jsonify({
                'success': True,
                'message': '文件夹创建成功',
                'path': path
            })
            
        except Exception as e:
            logger.error(f"创建文件夹错误: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/files/rename', methods=['POST'])
    def rename_item():
        """
        重命名文件或文件夹
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': '请求数据不能为空'
                })
            
            old_path = data.get('oldPath', '')
            new_path = data.get('newPath', '')
            mode = data.get('mode', 'workspace')
            
            if not old_path or not new_path:
                return jsonify({
                    'success': False,
                    'error': '旧路径和新路径都不能为空'
                })
            
            # 安全检查
            if not is_safe_filename(os.path.basename(new_path)):
                return jsonify({
                    'success': False,
                    'error': '无效的新名称'
                })
            
            # 根据模式选择基础路径
            base_path = get_base_path(mode)
            
            # 构建完整路径并验证
            full_old_path = os.path.join(base_path, old_path)
            full_new_path = os.path.join(base_path, new_path)
            
            validated_old_path = validate_path(full_old_path, base_path)
            validated_new_path = validate_path(full_new_path, base_path)
            
            if not validated_old_path:
                return jsonify({
                    'success': False,
                    'error': '无效的旧路径'
                })
            
            if not validated_new_path:
                return jsonify({
                    'success': False,
                    'error': '无效的新路径'
                })
            
            # 检查旧路径是否存在
            if not os.path.exists(validated_old_path):
                return jsonify({
                    'success': False,
                    'error': '要重命名的项目不存在'
                })
            
            # 检查新路径是否已存在
            if os.path.exists(validated_new_path):
                return jsonify({
                    'success': False,
                    'error': '目标名称已存在'
                })
            
            # 执行重命名
            os.rename(validated_old_path, validated_new_path)
            
            logger.info(f"重命名: {validated_old_path} -> {validated_new_path}")
            return jsonify({
                'success': True,
                'message': '重命名成功',
                'oldPath': old_path,
                'newPath': new_path
            })
            
        except Exception as e:
            logger.error(f"重命名错误: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/files/delete', methods=['DELETE'])
    def delete_item():
        """
        删除文件或文件夹
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': '请求数据不能为空'
                })
            
            path = data.get('path', '')
            mode = data.get('mode', 'workspace')
            
            if not path:
                return jsonify({
                    'success': False,
                    'error': '路径不能为空'
                })
            
            # 安全检查
            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的名称'
                })
            
            # 根据模式选择基础路径
            base_path = get_base_path(mode)
            
            # 构建完整路径并验证
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)
            
            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的路径'
                })
            
            # 检查是否存在
            if not os.path.exists(validated_path):
                return jsonify({
                    'success': False,
                    'error': '要删除的项目不存在'
                })
            
            # 执行删除
            if os.path.isdir(validated_path):
                shutil.rmtree(validated_path)
                logger.info(f"删除文件夹: {validated_path}")
            else:
                os.remove(validated_path)
                logger.info(f"删除文件: {validated_path}")
            
            return jsonify({
                'success': True,
                'message': '删除成功',
                'path': path
            })
            
        except Exception as e:
            logger.error(f"删除错误: {e}")
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
