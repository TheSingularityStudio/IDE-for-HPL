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
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLUtils;
}
