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
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLAPI;
}
