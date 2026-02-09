/**
 * HPL IDE - 工具函数模块
 * 提供通用的工具函数
 */

const HPLUtils = {
    /**
     * 安全的HTML转义函数，防止XSS攻击
     */
    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * 验证文件名合法性
     */
    isValidFilename(filename) {
        if (!filename || typeof filename !== 'string') return false;
        
        // 检查空字符串
        if (filename.trim() === '') return false;
        
        // 检查非法字符
        const invalidChars = /[<>:"/\\|?*\x00-\x1f]/;
        if (invalidChars.test(filename)) return false;
        
        // 检查保留名称（Windows）
        const reservedNames = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;
        const nameWithoutExt = filename.split('.')[0];
        if (reservedNames.test(nameWithoutExt)) return false;
        
        // 检查长度
        if (filename.length > 255) return false;
        
        return true;
    },

    /**
     * 创建带超时的 AbortController（浏览器兼容版本）
     */
    createTimeoutSignal(timeoutMs) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        
        return {
            signal: controller.signal,
            cleanup: () => clearTimeout(timeoutId)
        };
    },

    /**
     * 防抖函数
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * 节流函数
     */
    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * 路径处理工具函数 - 规范化路径
     * @param {string} path - 原始路径
     * @returns {string} 规范化后的路径
     */
    normalizePath(path) {
        if (!path || typeof path !== 'string') return '';
        
        // 统一使用正斜杠
        let normalized = path.replace(/\\/g, '/');
        
        // 移除多余斜杠
        normalized = normalized.replace(/\/+/g, '/');
        
        // 移除末尾斜杠（根目录除外）
        if (normalized.length > 1 && normalized.endsWith('/')) {
            normalized = normalized.slice(0, -1);
        }
        
        return normalized;
    },

    /**
     * 路径处理工具函数 - 拼接路径
     * @param {string} basePath - 基础路径
     * @param {string} relativePath - 相对路径
     * @returns {string} 拼接后的路径
     */
    joinPath(basePath, relativePath) {
        const normalizedBase = this.normalizePath(basePath);
        const normalizedRelative = this.normalizePath(relativePath);
        
        if (!normalizedBase) return normalizedRelative;
        if (!normalizedRelative) return normalizedBase;
        
        // 如果relativePath是绝对路径，直接返回
        if (normalizedRelative.startsWith('/') || normalizedRelative.includes(':/')) {
            return normalizedRelative;
        }
        
        return `${normalizedBase}/${normalizedRelative}`;
    },

    /**
     * 路径处理工具函数 - 获取文件名
     * @param {string} path - 完整路径
     * @returns {string} 文件名
     */
    getFilename(path) {
        const normalized = this.normalizePath(path);
        if (!normalized) return '';
        
        const parts = normalized.split('/');
        return parts[parts.length - 1] || '';
    },

    /**
     * 路径处理工具函数 - 获取父目录路径
     * @param {string} path - 完整路径
     * @returns {string} 父目录路径
     */
    getParentPath(path) {
        const normalized = this.normalizePath(path);
        if (!normalized) return '';
        
        const lastSlashIndex = normalized.lastIndexOf('/');
        if (lastSlashIndex <= 0) return '';
        
        return normalized.substring(0, lastSlashIndex);
    },

    /**
     * 路径处理工具函数 - 获取相对路径（从模式根目录）
     * @param {string} fullPath - 完整路径
     * @param {string} mode - 模式（workspace/examples）
     * @returns {string} 相对路径
     */
    getRelativePath(fullPath, mode) {
        const normalized = this.normalizePath(fullPath);
        if (!normalized) return '';
        
        // 如果路径以模式名开头，移除它
        const modePrefix = `${mode}/`;
        if (normalized.startsWith(modePrefix)) {
            return normalized.substring(modePrefix.length);
        }
        
        return normalized;
    },

    /**
     * 路径处理工具函数 - 构建API使用的路径
     * @param {string} folderPath - 文件夹路径
     * @param {string} filename - 文件名
     * @param {string} mode - 当前模式
     * @returns {string} API使用的相对路径
     */
    buildApiPath(folderPath, filename, mode) {
        // 规范化文件名
        const normalizedFilename = this.normalizePath(filename);
        
        // 如果在根目录
        if (!folderPath || folderPath === mode) {
            return normalizedFilename;
        }
        
        // 移除模式前缀
        const relativeFolder = this.getRelativePath(folderPath, mode);
        
        if (!relativeFolder) {
            return normalizedFilename;
        }
        
        return `${relativeFolder}/${normalizedFilename}`;
    },

    /**
     * 路径处理工具函数 - 检查路径是否在指定目录下
     * @param {string} path - 要检查的路径
     * @param {string} parentPath - 父目录路径
     * @returns {boolean} 是否在父目录下
     */
    isPathUnder(path, parentPath) {
        const normalizedPath = this.normalizePath(path);
        const normalizedParent = this.normalizePath(parentPath);
        
        if (!normalizedPath || !normalizedParent) return false;
        
        return normalizedPath.startsWith(normalizedParent + '/') || 
               normalizedPath === normalizedParent;
    }
};


// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLUtils;
}
