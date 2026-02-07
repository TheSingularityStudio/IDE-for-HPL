/**
 * HPL IDE 配置管理
 * 支持动态配置后端服务器地址
 */

const HPLConfig = {
    // 默认配置
    defaults: {
        // 后端服务器地址
        apiBaseUrl: 'http://localhost:5000',
        // 请求超时时间（毫秒）
        requestTimeout: 30000,
        // 是否启用自动保存
        autoSave: false,
        // 自动保存间隔（毫秒）
        autoSaveInterval: 5000,
        // 编辑器主题
        editorTheme: 'vs-dark',
        // 字体大小
        fontSize: 14,
        // 是否显示 minimap
        minimap: true,
        // 是否启用自动换行
        wordWrap: 'on'
    },

    // 配置存储键名
    storageKey: 'hpl-ide-config',

    /**
     * 获取当前配置
     * 合并默认配置和用户自定义配置
     */
    getConfig() {
        const stored = localStorage.getItem(this.storageKey);
        const userConfig = stored ? JSON.parse(stored) : {};
        return { ...this.defaults, ...userConfig };
    },

    /**
     * 保存配置
     */
    saveConfig(config) {
        const currentConfig = this.getConfig();
        const newConfig = { ...currentConfig, ...config };
        localStorage.setItem(this.storageKey, JSON.stringify(newConfig));
        return newConfig;
    },

    /**
     * 重置为默认配置
     */
    resetConfig() {
        localStorage.removeItem(this.storageKey);
        return this.defaults;
    },

    /**
     * 获取 API 基础 URL
     * 自动处理尾部斜杠
     */
    getApiBaseUrl() {
        const config = this.getConfig();
        let url = config.apiBaseUrl || this.defaults.apiBaseUrl;
        // 移除尾部斜杠
        url = url.replace(/\/+$/, '');
        return url;
    },

    /**
     * 构建完整 API URL
     * 自动添加 /api 前缀
     */
    buildApiUrl(endpoint) {
        const baseUrl = this.getApiBaseUrl();
        // 确保 endpoint 以 / 开头
        const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
        // 添加 /api 前缀
        return `${baseUrl}/api${cleanEndpoint}`;
    },


    /**
     * 测试后端连接
     */
    async testConnection() {
        try {
            const response = await fetch(this.buildApiUrl('/health'), {

                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                },
                // 使用较短的超时进行健康检查
                signal: AbortSignal.timeout(5000)
            });
            
            if (response.ok) {
                const data = await response.json();
                return { success: true, data };
            } else {
                return { success: false, error: `HTTP ${response.status}` };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
};

// 导出配置对象
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLConfig;
}
