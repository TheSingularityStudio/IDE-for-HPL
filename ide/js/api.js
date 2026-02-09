/**
 * HPL IDE - API 通信模块
 * 管理与后端服务器的所有通信
 */

const HPLAPI = {
    /**
     * 测试服务器连接
     */
    async testConnection() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            const response = await fetch(HPLConfig.buildApiUrl('/health'), {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                },
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                const data = await response.json();
                return { success: true, data };
            } else {
                return { success: false, error: `HTTP ${response.status}` };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    /**
     * 执行 HPL 代码
     */
    async runCode(code) {
        const formData = new FormData();
        formData.append('code', code);
        
        const timeoutConfig = HPLConfig.getConfig().requestTimeout || 7000;
        const { signal, cleanup } = HPLUtils.createTimeoutSignal(timeoutConfig);
        
        try {
            const response = await fetch(HPLConfig.buildApiUrl('/run'), {
                method: 'POST',
                body: formData,
                signal: signal
            });
            
            cleanup();
            return await response.json();
        } catch (error) {
            cleanup();
            throw error;
        }
    },

    /**
     * 获取示例文件列表
     */
    async listExamples() {
        const response = await fetch(HPLConfig.buildApiUrl('/examples'));
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '获取文件列表失败');
        }
        
        return result.examples;
    },

    /**
     * 加载示例文件内容
     */
    async loadExample(filename) {
        if (!filename) {
            throw new Error('文件名不能为空');
        }
        
        const response = await fetch(
            HPLConfig.buildApiUrl(`/examples/${encodeURIComponent(filename)}`)
        );
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '未知错误');
        }
        
        return result;
    },

    /**
     * 获取文件树
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async getFileTree(mode = 'workspace') {
        const response = await fetch(
            HPLConfig.buildApiUrl(`/files/tree?mode=${encodeURIComponent(mode)}`)
        );
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '获取文件树失败');
        }
        
        return result.tree;
    },

    /**
     * 读取文件内容
     * @param {string} path - 文件路径
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async readFile(path, mode = 'workspace') {
        if (!path) {
            throw new Error('文件路径不能为空');
        }
        
        const response = await fetch(
            HPLConfig.buildApiUrl(`/files/read?path=${encodeURIComponent(path)}&mode=${encodeURIComponent(mode)}`)
        );
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '读取文件失败');
        }
        
        return result;
    },



    /**
     * 创建新文件
     * @param {string} path - 文件路径
     * @param {string} content - 文件内容
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async createFile(path, content = '', mode = 'workspace') {
        const response = await fetch(HPLConfig.buildApiUrl('/files/create'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, content, mode })
        });

        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '创建文件失败');
        }
        
        return result;
    },

    /**
     * 保存文件（创建或更新）
     * @param {string} path - 文件路径
     * @param {string} content - 文件内容
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async saveFile(path, content = '', mode = 'workspace') {
        if (!path) {
            throw new Error('文件路径不能为空');
        }
        
        const response = await fetch(HPLConfig.buildApiUrl('/files/save'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, content, mode })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '保存文件失败');
        }
        
        return result;
    },

    /**
     * 创建新文件夹
     * @param {string} path - 文件夹路径
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async createFolder(path, mode = 'workspace') {
        const response = await fetch(HPLConfig.buildApiUrl('/folders/create'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, mode })
        });

        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '创建文件夹失败');
        }
        
        return result;
    },

    /**
     * 重命名文件或文件夹
     * @param {string} oldPath - 旧路径
     * @param {string} newPath - 新路径
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async renameItem(oldPath, newPath, mode = 'workspace') {
        const response = await fetch(HPLConfig.buildApiUrl('/files/rename'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ oldPath, newPath, mode })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '重命名失败');
        }
        
        return result;
    },


    /**
     * 删除文件或文件夹
     * @param {string} path - 文件或文件夹路径
     * @param {string} mode - 'workspace' 或 'examples'
     */
    async deleteItem(path, mode = 'workspace') {
        const response = await fetch(HPLConfig.buildApiUrl('/files/delete'), {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, mode })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '删除失败');
        }
        
        return result;
    },

    // ==================== 文件备份 API ====================

    /**
     * 创建文件备份
     * @param {string} path - 文件路径
     */
    async backupFile(path) {
        if (!path) {
            throw new Error('文件路径不能为空');
        }
        
        const response = await fetch(HPLConfig.buildApiUrl('/files/backup'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '创建备份失败');
        }
        
        return result;
    },

    /**
     * 获取文件备份列表
     * @param {string} path - 文件路径（可选，不传则返回所有备份）
     */
    async getBackups(path = '') {
        const url = path 
            ? HPLConfig.buildApiUrl(`/files/backups?path=${encodeURIComponent(path)}`)
            : HPLConfig.buildApiUrl('/files/backups');
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '获取备份列表失败');
        }
        
        return result;
    },

    /**
     * 从备份恢复文件
     * @param {string} backupFilename - 备份文件名
     * @param {string} targetPath - 目标路径（可选）
     */
    async restoreFile(backupFilename, targetPath = '') {
        if (!backupFilename) {
            throw new Error('备份文件名不能为空');
        }
        
        const response = await fetch(HPLConfig.buildApiUrl('/files/restore'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ backup_filename: backupFilename, target_path: targetPath })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '恢复备份失败');
        }
        
        return result;
    },

    /**
     * 删除指定备份
     * @param {string} backupFilename - 备份文件名
     */
    async deleteBackup(backupFilename) {
        if (!backupFilename) {
            throw new Error('备份文件名不能为空');
        }
        
        const response = await fetch(HPLConfig.buildApiUrl('/files/backup'), {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ backup_filename: backupFilename })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || '删除备份失败');
        }
        
        return result;
    }

};


// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLAPI;
}
