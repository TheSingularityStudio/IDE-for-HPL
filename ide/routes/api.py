"""
API路由模块
提供所有REST API端点
"""

import os
import shutil
import tempfile
import logging
from datetime import datetime
from flask import Flask, request, jsonify


from config import (
    MAX_REQUEST_SIZE, MAX_EXECUTION_TIME, 
    ALLOWED_WORKSPACE_DIR, ALLOWED_EXAMPLES_DIR, SERVER_VERSION,
    BACKUP_DIR, MAX_BACKUP_COUNT
)


# P0修复：使用新的执行工具（进程隔离 + 资源限制）
from ide.utils.execution_utils import execute_with_process_timeout, ExecutionTimeoutError
from ide.services.sandbox_executor import execute_in_sandbox, execute_code_in_sandbox
from ide.utils.temp_manager import temp_directory, TempManager

from ide.services.security import limit_request_size, validate_path, is_safe_filename

from ide.services.code_processor import clean_code, copy_include_files

# P0修复：从统一运行时管理器导入
from ide.services.runtime_manager import check_runtime_available

from ide.services.syntax_validator import validate_code




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
        P0修复：使用进程隔离和资源限制
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
        
        # P0修复：使用TempManager上下文管理器确保清理
        try:
            with temp_directory(prefix='hpl_exec_') as temp_dir:
                # 复制 include 文件到临时目录
                temp_include_files, code, not_found_includes = copy_include_files(code, temp_dir)
                
                # 如果有未找到的 include 文件，记录警告
                if not_found_includes:
                    logger.warning(f"未找到的 include 文件: {', '.join(not_found_includes)}")

                # 创建临时 HPL 文件
                temp_file = os.path.join(temp_dir, 'main.hpl')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                logger.info(f"执行临时文件: {temp_file}")
                
                # P0修复：使用沙箱执行（带资源限制和进程隔离）
                result = execute_in_sandbox(
                    temp_file,
                    timeout=MAX_EXECUTION_TIME,
                    max_memory_mb=100,  # 100MB内存限制
                    max_cpu_time=MAX_EXECUTION_TIME  # CPU时间限制
                )
                
                return jsonify(result)
                
        except Exception as e:
            logger.error(f"服务器错误: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'服务器错误: {str(e)}'
            })

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

    @app.route('/api/files/read', methods=['GET'])
    def read_file():
        """
        读取文件内容
        支持 workspace 和 examples 目录
        """
        try:
            path = request.args.get('path', '')
            mode = request.args.get('mode', 'workspace')
            
            if not path:
                return jsonify({
                    'success': False,
                    'error': '文件路径不能为空'
                })
            
            # 安全检查：防止目录遍历
            if not is_safe_filename(os.path.basename(path)):
                logger.warning(f"非法文件名尝试: {path}")
                return jsonify({
                    'success': False,
                    'error': '无效的文件名'
                })
            
            # 根据模式选择基础路径
            base_path = get_base_path(mode)
            
            # 构建完整路径并验证
            file_path = os.path.join(base_path, path)
            validated_path = validate_path(file_path, base_path)
            
            if not validated_path:
                return jsonify({
                    'success': False,
                    'error': '无效的文件路径'
                })
            
            # 检查文件是否存在
            if not os.path.exists(validated_path) or not os.path.isfile(validated_path):
                return jsonify({
                    'success': False,
                    'error': '文件不存在'
                })
            
            # 读取文件内容
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

    @app.route('/api/files/save', methods=['POST'])
    def save_file():
        """
        保存文件（创建或更新）
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
            
            # 确保父目录存在
            parent_dir = os.path.dirname(validated_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            # 保存文件（创建或覆盖）
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

    @app.route('/api/validate', methods=['POST'])
    @limit_request_size(MAX_REQUEST_SIZE)
    def validate_syntax():
        """
        语法验证端点
        静态分析HPL代码，不执行代码只检查语法错误
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
        
        # 清理代码中的转义字符
        code = clean_code(code)
        
        try:
            # 执行语法验证
            result = validate_code(code)
            result['success'] = True
            
            logger.info(f"语法验证完成: {result['total_errors']} 个错误, {result['total_warnings']} 个警告")
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"语法验证失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'语法验证失败: {str(e)}',
                'valid': False,
                'errors': [],
                'warnings': []
            }), 500

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """
        健康检查端点
        P0修复：添加运行时状态和资源限制信息
        """
        from ide.services.runtime_manager import get_runtime_info
        
        runtime_info = get_runtime_info()
        
        return jsonify({
            'status': 'ok',
            'message': 'HPL IDE Server is running',
            'version': SERVER_VERSION,
            'max_execution_time': MAX_EXECUTION_TIME,
            'max_request_size': MAX_REQUEST_SIZE,
            'runtime': {
                'available': runtime_info.get('available', False),
                'version': runtime_info.get('version', 'unknown')
            },
            'resource_limits': {
                'memory_mb': 100,  # 沙箱内存限制
                'cpu_time': MAX_EXECUTION_TIME,
                'file_size_mb': 10
            }
        })

    # ==================== 文件备份 API ====================

    def ensure_backup_dir():
        """确保备份目录存在"""
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)

    def get_backup_filename(original_path):
        """生成备份文件名"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # 将路径中的斜杠替换为下划线，避免目录嵌套
        safe_path = original_path.replace('/', '_').replace('\\', '_')
        return f"{safe_path}.{timestamp}.backup"

    @app.route('/api/files/backup', methods=['POST'])
    def backup_file():
        """
        创建文件备份
        请求体: { path: '相对路径' }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '请求数据不能为空'}), 400
            
            path = data.get('path', '')
            if not path:
                return jsonify({'success': False, 'error': '文件路径不能为空'}), 400
            
            # 安全检查
            if not is_safe_filename(os.path.basename(path)):
                return jsonify({'success': False, 'error': '无效的文件名'}), 400
            
            # 构建完整路径并验证
            file_path = os.path.join(ALLOWED_WORKSPACE_DIR, path)
            validated_path = validate_path(file_path, ALLOWED_WORKSPACE_DIR)
            
            if not validated_path or not os.path.isfile(validated_path):
                return jsonify({'success': False, 'error': '文件不存在'}), 404
            
            # 确保备份目录存在
            ensure_backup_dir()
            
            # 生成备份文件名
            backup_filename = get_backup_filename(path)
            backup_path = os.path.join(BACKUP_DIR, backup_filename)
            
            # 复制文件到备份目录
            shutil.copy2(validated_path, backup_path)
            
            # 清理旧备份（保留最近 MAX_BACKUP_COUNT 个）
            cleanup_old_backups(path)
            
            logger.info(f"创建备份: {path} -> {backup_filename}")
            
            return jsonify({
                'success': True,
                'message': '备份创建成功',
                'backup': {
                    'filename': backup_filename,
                    'path': backup_path,
                    'original': path,
                    'created_at': datetime.now().isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    def cleanup_old_backups(original_path):
        """清理旧备份，只保留最近的 MAX_BACKUP_COUNT 个"""
        try:
            safe_prefix = original_path.replace('/', '_').replace('\\', '_')
            backup_files = []
            
            for filename in os.listdir(BACKUP_DIR):
                if filename.startswith(safe_prefix) and filename.endswith('.backup'):
                    filepath = os.path.join(BACKUP_DIR, filename)
                    backup_files.append({
                        'filename': filename,
                        'path': filepath,
                        'mtime': os.path.getmtime(filepath)
                    })
            
            # 按修改时间排序（最新的在前）
            backup_files.sort(key=lambda x: x['mtime'], reverse=True)
            
            # 删除超出限制的备份
            for backup in backup_files[MAX_BACKUP_COUNT:]:
                os.remove(backup['path'])
                logger.info(f"清理旧备份: {backup['filename']}")
                
        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")

    @app.route('/api/files/backups', methods=['GET'])
    def list_backups():
        """
        获取文件的备份列表
        查询参数: path=文件路径
        """
        try:
            path = request.args.get('path', '')
            
            if not path:
                # 返回所有备份
                backups = []
                if os.path.exists(BACKUP_DIR):
                    for filename in os.listdir(BACKUP_DIR):
                        if filename.endswith('.backup'):
                            filepath = os.path.join(BACKUP_DIR, filename)
                            # 解析原始文件路径
                            parts = filename.rsplit('.', 2)  # [original, timestamp, backup]
                            if len(parts) == 3:
                                original = parts[0].replace('_', '/')
                                backups.append({
                                    'filename': filename,
                                    'original': original,
                                    'created_at': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                                    'size': os.path.getsize(filepath)
                                })
                
                backups.sort(key=lambda x: x['created_at'], reverse=True)
                return jsonify({'success': True, 'backups': backups})
            
            # 返回指定文件的备份
            if not is_safe_filename(os.path.basename(path)):
                return jsonify({'success': False, 'error': '无效的文件名'}), 400
            
            safe_prefix = path.replace('/', '_').replace('\\', '_')
            backups = []
            
            if os.path.exists(BACKUP_DIR):
                for filename in os.listdir(BACKUP_DIR):
                    if filename.startswith(safe_prefix) and filename.endswith('.backup'):
                        filepath = os.path.join(BACKUP_DIR, filename)
                        parts = filename.rsplit('.', 2)
                        if len(parts) == 3:
                            timestamp = parts[1]
                            backups.append({
                                'filename': filename,
                                'original': path,
                                'timestamp': timestamp,
                                'created_at': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                                'size': os.path.getsize(filepath)
                            })
            
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            return jsonify({'success': True, 'backups': backups, 'original': path})
            
        except Exception as e:
            logger.error(f"获取备份列表失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/files/restore', methods=['POST'])
    def restore_backup():
        """
        从备份恢复文件
        请求体: { backup_filename: '备份文件名', target_path: '目标路径（可选）' }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '请求数据不能为空'}), 400
            
            backup_filename = data.get('backup_filename', '')
            target_path = data.get('target_path', '')
            
            if not backup_filename:
                return jsonify({'success': False, 'error': '备份文件名不能为空'}), 400
            
            # 安全检查
            if not is_safe_filename(backup_filename):
                return jsonify({'success': False, 'error': '无效的备份文件名'}), 400
            
            # 构建备份文件路径
            backup_path = os.path.join(BACKUP_DIR, backup_filename)
            
            if not os.path.exists(backup_path) or not os.path.isfile(backup_path):
                return jsonify({'success': False, 'error': '备份文件不存在'}), 404
            
            # 如果没有指定目标路径，从备份文件名解析
            if not target_path:
                parts = backup_filename.rsplit('.', 2)
                if len(parts) == 3:
                    target_path = parts[0].replace('_', '/')
            
            if not target_path:
                return jsonify({'success': False, 'error': '无法确定目标路径'}), 400
            
            # 验证目标路径
            if not is_safe_filename(os.path.basename(target_path)):
                return jsonify({'success': False, 'error': '无效的目标文件名'}), 400
            
            full_target_path = os.path.join(ALLOWED_WORKSPACE_DIR, target_path)
            validated_target = validate_path(full_target_path, ALLOWED_WORKSPACE_DIR)
            
            if not validated_target:
                return jsonify({'success': False, 'error': '无效的目标路径'}), 400
            
            # 确保目标目录存在
            parent_dir = os.path.dirname(validated_target)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            # 恢复文件
            shutil.copy2(backup_path, validated_target)
            
            logger.info(f"恢复备份: {backup_filename} -> {target_path}")
            
            return jsonify({
                'success': True,
                'message': '文件恢复成功',
                'restored_to': target_path
            })
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/files/backup', methods=['DELETE'])
    def delete_backup():
        """
        删除指定备份
        请求体: { backup_filename: '备份文件名' }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '请求数据不能为空'}), 400
            
            backup_filename = data.get('backup_filename', '')
            
            if not backup_filename:
                return jsonify({'success': False, 'error': '备份文件名不能为空'}), 400
            
            # 安全检查
            if not is_safe_filename(backup_filename):
                return jsonify({'success': False, 'error': '无效的备份文件名'}), 400
            
            # 构建备份文件路径
            backup_path = os.path.join(BACKUP_DIR, backup_filename)
            
            # 验证路径在备份目录内
            if not backup_path.startswith(BACKUP_DIR):
                return jsonify({'success': False, 'error': '无效的路径'}), 400
            
            if not os.path.exists(backup_path):
                return jsonify({'success': False, 'error': '备份文件不存在'}), 404
            
            # 删除备份
            os.remove(backup_path)
            
            logger.info(f"删除备份: {backup_filename}")
            
            return jsonify({
                'success': True,
                'message': '备份已删除'
            })
            
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
