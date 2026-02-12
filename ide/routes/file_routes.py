"""
文件操作路由
处理文件和文件夹的创建、读取、保存、重命名和删除
"""

import os
import shutil
import logging
from flask import request, jsonify

from ide.services.code_service import validate_path, is_safe_filename
from config import ALLOWED_WORKSPACE_DIR

logger = logging.getLogger(__name__)


def get_base_path(mode):
    """
    根据模式获取基础路径
    """
    if mode == 'workspace':
        return ALLOWED_WORKSPACE_DIR
    return ALLOWED_WORKSPACE_DIR  # 默认使用workspace


def register_file_routes(app):
    """
    注册文件操作路由

    Args:
        app: Flask应用实例
    """

    @app.route('/api/files/tree', methods=['GET'])
    def get_file_tree():
        """
        获取文件树结构
        """
        mode = request.args.get('mode', 'workspace')
        base_path = get_base_path(mode)

        def build_tree(path, base_path):
            try:
                rel_path = os.path.relpath(path, base_path)
                name = os.path.basename(path)

                if os.path.isdir(path):
                    children = []
                    try:
                        for item in sorted(os.listdir(path)):
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
                    'error': f'目录不存在'
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

    @app.route('/api/files/read', methods=['GET'])
    def read_file():
        """
        读取文件内容
        """
        try:
            path = request.args.get('path', '')
            mode = request.args.get('mode', 'workspace')

            if not path:
                return jsonify({
                    'success': False,
                    'error': '文件路径不能为空'
                })

            if not is_safe_filename(os.path.basename(path)):
                logger.warning(f"非法文件名尝试: {path}")
                return jsonify({
                    'success': False,
                    'error': '无效的文件名'
                })

            base_path = get_base_path(mode)
            file_path = os.path.join(base_path, path)
            validated_path = validate_path(file_path, base_path)

            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件路径'
                })

            if not os.path.exists(validated_path) or not os.path.isfile(validated_path):
                return jsonify({
                    'success': False,
                    'error': '文件不存在'
                })

            with open(validated_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"读取文件: {validated_path}")
            return jsonify({
                'success': True,
                'content': content,
                'name': os.path.basename(path),
                'path': path
            })

        except Exception as e:
            logger.error(f"读取文件错误: {e}")
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

            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的文件名'
                })

            base_path = get_base_path(mode)
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)

            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件路径'
                })

            if os.path.exists(validated_path):
                return jsonify({
                    'success': False,
                    'error': '文件已存在'
                })

            parent_dir = os.path.dirname(validated_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

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

    @app.route('/api/files/save', methods=['POST'])
    def save_file():
        """
        保存文件
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

            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的文件名'
                })

            base_path = get_base_path(mode)
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)

            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件路径'
                })

            parent_dir = os.path.dirname(validated_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(validated_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"保存文件: {validated_path}")
            return jsonify({
                'success': True,
                'message': '文件保存成功',
                'path': path
            })

        except Exception as e:
            logger.error(f"保存文件错误: {e}")
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

            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的文件夹名'
                })

            base_path = get_base_path(mode)
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)

            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件夹路径'
                })

            if os.path.exists(validated_path):
                return jsonify({
                    'success': False,
                    'error': '文件夹已存在'
                })

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

            if not is_safe_filename(os.path.basename(new_path)):
                return jsonify({
                    'success': False,
                    'error': '无效的新名称'
                })

            base_path = get_base_path(mode)
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

            if not os.path.exists(validated_old_path):
                return jsonify({
                    'success': False,
                    'error': '要重命名的项目不存在'
                })

            if os.path.exists(validated_new_path):
                return jsonify({
                    'success': False,
                    'error': '目标名称已存在'
                })

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

            if not is_safe_filename(os.path.basename(path)):
                return jsonify({
                    'success': False,
                    'error': '无效的名称'
                })

            base_path = get_base_path(mode)
            full_path = os.path.join(base_path, path)
            validated_path = validate_path(full_path, base_path)

            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的路径'
                })

            if not os.path.exists(validated_path):
                return jsonify({
                    'success': False,
                    'error': '要删除的项目不存在'
                })

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
