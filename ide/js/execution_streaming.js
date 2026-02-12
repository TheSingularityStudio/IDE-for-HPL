/**
 * P1修复：流式执行模块
 * 使用Server-Sent Events (SSE) 实现实时输出
 */

class ExecutionStreaming {
    constructor() {
        this.eventSource = null;
        this.outputBuffer = '';
        this.onOutputCallback = null;
        this.onErrorCallback = null;
        this.onDoneCallback = null;
        this.isRunning = false;
    }

    /**
     * 执行代码并实时获取输出
     * @param {string} code - HPL代码
     * @param {Array|string} inputData - 输入数据（可选）
     * @param {Object} callbacks - 回调函数
     * @param {Function} callbacks.onOutput - 收到输出时调用
     * @param {Function} callbacks.onError - 发生错误时调用
     * @param {Function} callbacks.onDone - 执行完成时调用
     */
    executeStreaming(code, inputData = null, callbacks = {}) {
        // 如果已有执行在进行，先停止
        this.stop();

        this.onOutputCallback = callbacks.onOutput || (() => {});
        this.onErrorCallback = callbacks.onError || (() => {});
        this.onDoneCallback = callbacks.onDone || (() => {});
        this.outputBuffer = '';
        this.isRunning = true;

        // 准备请求数据
        const formData = new FormData();
        formData.append('code', code);
        
        if (inputData) {
            if (Array.isArray(inputData)) {
                formData.append('input_data', JSON.stringify(inputData));
            } else {
                formData.append('input_data', inputData);
            }
        }

        // 使用fetch API发送POST请求获取SSE流
        fetch('/api/run/stream', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 获取reader来读取流
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            const processStream = () => {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        this._handleDone();
                        return;
                    }
                    
                    // 解码并处理数据
                    const chunk = decoder.decode(value, { stream: true });
                    this._processSSEChunk(chunk);
                    
                    // 继续读取
                    return processStream();
                });
            };
            
            return processStream();
        })
        .catch(error => {
            this.isRunning = false;
            this.onErrorCallback({
                type: 'connection_error',
                data: error.message
            });
        });
    }

    /**
     * 处理SSE数据块
     * @private
     */
    _processSSEChunk(chunk) {
        // SSE格式: data: {...}\n\n
        const lines = chunk.split('\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const jsonStr = line.substring(6); // 去掉 "data: " 前缀
                    const data = JSON.parse(jsonStr);
                    this._handleMessage(data);
                } catch (e) {
                    console.error('解析SSE数据失败:', e, line);
                }
            }
        }
    }

    /**
     * 处理单个消息
     * @private
     */
    _handleMessage(data) {
        switch (data.type) {
            case 'stdout':
                this.outputBuffer += data.data;
                this.onOutputCallback(data.data, this.outputBuffer);
                break;
                
            case 'stderr':
                this.outputBuffer += data.data;
                this.onOutputCallback(data.data, this.outputBuffer);
                break;
                
            case 'error':
                this.isRunning = false;
                this.onErrorCallback(data);
                break;
                
            case 'done':
                this._handleDone();
                break;
                
            case 'heartbeat':
                // 心跳包，保持连接活跃
                break;
                
            default:
                console.log('未知消息类型:', data.type, data);
        }
    }

    /**
     * 处理执行完成
     * @private
     */
    _handleDone() {
        if (this.isRunning) {
            this.isRunning = false;
            this.onDoneCallback({
                success: true,
                output: this.outputBuffer
            });
        }
    }

    /**
     * 停止当前执行
     */
    stop() {
        this.isRunning = false;
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    /**
     * 检查是否正在执行
     * @returns {boolean}
     */
    isExecuting() {
        return this.isRunning;
    }

    /**
     * 获取当前输出缓冲区内容
     * @returns {string}
     */
    getOutput() {
        return this.outputBuffer;
    }

    /**
     * 清空输出缓冲区
     */
    clearOutput() {
        this.outputBuffer = '';
    }
}

// 创建全局实例
const executionStreaming = new ExecutionStreaming();

// 向后兼容的便捷函数
function runCodeStreaming(code, inputData, callbacks) {
    return executionStreaming.executeStreaming(code, inputData, callbacks);
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ExecutionStreaming, executionStreaming, runCodeStreaming };
}
