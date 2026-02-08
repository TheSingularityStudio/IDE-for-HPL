/**
 * HPL IDE 配置管理
 * 支持动态配置后端服务器地址
 */

const HPLConfig = {
    // 默认配置
    defaults: {
        // 后端服务器地址
        apiBaseUrl: 'http://localhost:5000',
        // 请求超时时间（毫秒）- 应与后端 MAX_EXECUTION_TIME 匹配（5秒 + 2秒缓冲）
        requestTimeout: 7000,


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
     * 验证配置项
     */
    validateConfig(config) {
        const errors = [];
        
        // 验证 API URL
        if (config.apiBaseUrl !== undefined) {
            if (!config.apiBaseUrl || typeof config.apiBaseUrl !== 'string') {
                errors.push('API 地址不能为空');
            } else {
                try {
                    new URL(config.apiBaseUrl);
                } catch (e) {
                    errors.push('API 地址格式不正确');
                }
            }
        }
        
        // 验证超时时间
        if (config.requestTimeout !== undefined) {
            const timeout = parseInt(config.requestTimeout);
            if (isNaN(timeout) || timeout < 5000) {
                errors.push('请求超时时间不能小于 5000 毫秒');
            } else if (timeout > 120000) {
                errors.push('请求超时时间不能大于 120000 毫秒');
            }
        }
        
        // 验证字体大小
        if (config.fontSize !== undefined) {
            const fontSize = parseInt(config.fontSize);
            if (isNaN(fontSize) || fontSize < 8) {
                errors.push('字体大小不能小于 8');
            } else if (fontSize > 32) {
                errors.push('字体大小不能大于 32');
            }
        }
        
        // 验证主题
        if (config.editorTheme !== undefined) {
            const allowedThemes = ['vs-dark', 'vs', 'hc-black'];
            if (!allowedThemes.includes(config.editorTheme)) {
                errors.push(`主题必须是以下之一: ${allowedThemes.join(', ')}`);
            }
        }
        
        // 验证自动保存
        if (config.autoSave !== undefined) {
            if (typeof config.autoSave !== 'boolean') {
                errors.push('自动保存必须是布尔值');
            }
        }
        
        return errors;
    },

    /**
     * 保存配置
     */
    saveConfig(config) {
        // 验证配置
        const errors = this.validateConfig(config);
        if (errors.length > 0) {
            throw new Error('配置验证失败: ' + errors.join(', '));
        }
        
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
            // 创建 AbortController 实现超时（兼容 Firefox/Safari）
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            const response = await fetch(this.buildApiUrl('/health'), {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                },
                // 使用 AbortController 实现超时
                signal: controller.signal
            });
            
            // 请求成功，清除超时
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
    }

};

// 导出配置对象
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLConfig;
}
