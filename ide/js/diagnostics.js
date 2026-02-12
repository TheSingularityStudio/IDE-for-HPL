/**
 * HPL语法诊断模块
 * 提供实时语法检查功能，集成Monaco Editor
 */

const HPLDiagnostics = {
    // 配置
    config: {
        enabled: true,
        autoCheck: true,
        debounceTime: 500, // 毫秒
        showWarnings: true,
        showInfos: false
    },
    
    // 状态
    state: {
        isChecking: false,
        lastCheckTime: 0,
        pendingCheck: null,
        currentMarkers: []
    },
    
    // Monaco editor实例
    editor: null,
    
    /**
     * 初始化诊断模块
     * @param {Object} editor - Monaco editor实例
     */
    init(editor) {
        this.editor = editor;
        
        // 注册诊断提供者
        this.registerDiagnosticsProvider();
        
        // 设置编辑器内容变更监听
        this.setupContentChangeListener();
        
        console.log('HPL Diagnostics 模块已初始化');
    },
    
    /**
     * 注册Monaco诊断提供者
     */
    registerDiagnosticsProvider() {
        if (!window.monaco) {
            console.error('Monaco未加载，无法注册诊断提供者');
            return;
        }
        
        // 注册代码动作提供者（用于快速修复）
        monaco.languages.registerCodeActionProvider('hpl', {
            provideCodeActions: (model, range, context, token) => {
                const actions = [];
                
                // 为每个标记提供快速修复
                context.markers.forEach(marker => {
                    if (marker.code === 'unclosed-string') {
                        actions.push({
                            title: '添加缺失的引号',
                            diagnostics: [marker],
                            kind: 'quickfix',
                            edit: {
                                edits: [{
                                    resource: model.uri,
                                    edit: {
                                        range: {
                                            startLineNumber: marker.endLineNumber,
                                            startColumn: marker.endColumn,
                                            endLineNumber: marker.endLineNumber,
                                            endColumn: marker.endColumn
                                        },
                                        text: '"'
                                    }
                                }]
                            },
                            isPreferred: true
                        });
                    }
                });
                
                return {
                    actions: actions,
                    dispose: () => {}
                };
            }
        });
    },
    
    /**
     * 检查当前文件是否为HPL文件
     * @returns {boolean} 是否为HPL文件
     */
    isHPLFile() {
        const currentFile = HPLFileManager.getCurrentFile();
        if (!currentFile) return false;
        return currentFile.toLowerCase().endsWith('.hpl');
    },

    /**
     * 设置内容变更监听
     */
    setupContentChangeListener() {
        if (!this.editor) return;
        
        // 监听内容变化
        this.editor.onDidChangeModelContent((e) => {
            if (!this.config.autoCheck) return;
            
            // 只对HPL文件进行自动检查
            if (!this.isHPLFile()) return;
            
            // 清除之前的待检查
            if (this.state.pendingCheck) {
                clearTimeout(this.state.pendingCheck);
            }
            
            // 设置新的待检查（防抖）
            this.state.pendingCheck = setTimeout(() => {
                this.checkSyntax();
            }, this.config.debounceTime);
        });
    },

    
    /**
     * 执行语法检查
     * @returns {Promise} 检查结果
     */
    async checkSyntax() {
        if (!this.editor || this.state.isChecking) {
            return;
        }
        
        // 只对HPL文件进行语法检查
        if (!this.isHPLFile()) {
            this.clearDiagnostics();
            this.updateStatusBar({ valid: true, total_errors: 0, total_warnings: 0, isNonHPL: true });
            return;
        }
        
        const code = this.editor.getValue();
        
        // 如果代码为空，清除所有标记
        if (!code.trim()) {
            this.clearDiagnostics();
            return;
        }
        
        this.state.isChecking = true;
        this.state.lastCheckTime = Date.now();
        
        try {
            const result = await this.validateCode(code);
            
            if (result.success) {
                this.updateDiagnostics(result);
                this.updateProblemsPanel(result);
            } else {
                console.error('语法验证失败:', result.error);
            }
        } catch (error) {
            console.error('语法检查出错:', error);
        } finally {
            this.state.isChecking = false;
        }
    },

    
    /**
     * 调用API验证代码
     * @param {string} code - HPL代码
     * @returns {Promise} 验证结果
     */
    async validateCode(code) {
        const formData = new FormData();
        formData.append('code', code);
        
        const response = await fetch('/api/validate', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    },
    
    /**
     * 更新编辑器诊断标记
     * @param {Object} result - 验证结果
     */
    updateDiagnostics(result) {
        if (!this.editor || !window.monaco) return;
        
        const model = this.editor.getModel();
        if (!model) return;
        
        // 转换错误为Monaco标记格式
        const markers = [];
        
        // 处理错误
        if (result.errors) {
            result.errors.forEach(error => {
                markers.push(this.createMarker(error, monaco.MarkerSeverity.Error));
            });
        }
        
        // 处理警告
        if (result.warnings && this.config.showWarnings) {
            result.warnings.forEach(warning => {
                markers.push(this.createMarker(warning, monaco.MarkerSeverity.Warning));
            });
        }
        
        // 设置模型标记
        monaco.editor.setModelMarkers(model, 'hpl', markers);
        this.state.currentMarkers = markers;
        
        // 更新状态栏
        this.updateStatusBar(result);
    },
    
    /**
     * 创建Monaco标记
     * @param {Object} item - 错误/警告项
     * @param {number} severity - 严重程度
     * @returns {Object} Monaco标记对象
     */
    createMarker(item, severity) {
        return {
            severity: severity,
            message: item.message,
            startLineNumber: item.line || 1,
            startColumn: item.column || 1,
            endLineNumber: item.line || 1,
            endColumn: item.column ? item.column + 1 : 1000,
            code: item.code || '',
            source: 'HPL语法检查'
        };
    },
    
    /**
     * 清除所有诊断标记
     */
    clearDiagnostics() {
        if (!this.editor || !window.monaco) return;
        
        const model = this.editor.getModel();
        if (model) {
            monaco.editor.setModelMarkers(model, 'hpl', []);
        }
        
        this.state.currentMarkers = [];
        this.updateStatusBar({ valid: true, total_errors: 0, total_warnings: 0 });
    },
    
    /**
     * 更新问题面板
     * @param {Object} result - 验证结果
     */
    updateProblemsPanel(result) {
        const panel = document.getElementById('problems-panel');
        if (!panel) return;
        
        const content = panel.querySelector('.problems-content');
        if (!content) return;
        
        // 清空内容
        content.innerHTML = '';
        
        // 如果没有错误和警告
        if ((!result.errors || result.errors.length === 0) && 
            (!result.warnings || result.warnings.length === 0)) {
            content.innerHTML = '<div class="no-problems">✅ 未发现语法问题</div>';
            panel.classList.remove('has-problems');
            return;
        }
        
        panel.classList.add('has-problems');
        
        // 创建问题列表
        const list = document.createElement('ul');
        list.className = 'problems-list';
        
        // 添加错误
        if (result.errors) {
            result.errors.forEach(error => {
                const item = this.createProblemItem(error, 'error');
                list.appendChild(item);
            });
        }
        
        // 添加警告
        if (result.warnings) {
            result.warnings.forEach(warning => {
                const item = this.createProblemItem(warning, 'warning');
                list.appendChild(item);
            });
        }
        
        content.appendChild(list);
    },
    
    /**
     * 创建问题项
     * @param {Object} item - 问题数据
     * @param {string} type - 类型 (error/warning)
     * @returns {HTMLElement} 问题项元素
     */
    createProblemItem(item, type) {
        const li = document.createElement('li');
        li.className = `problem-item problem-${type}`;
        li.dataset.line = item.line;
        li.dataset.column = item.column;
        
        const icon = type === 'error' ? '❌' : '⚠️';
        
        li.innerHTML = `
            <span class="problem-icon">${icon}</span>
            <span class="problem-location">第${item.line}行</span>
            <span class="problem-message">${HPLUtils.escapeHtml(item.message)}</span>
        `;
        
        // 点击跳转到对应位置
        li.addEventListener('click', () => {
            this.jumpToLocation(item.line, item.column);
        });
        
        return li;
    },
    
    /**
     * 跳转到指定位置
     * @param {number} line - 行号
     * @param {number} column - 列号
     */
    jumpToLocation(line, column) {
        if (!this.editor) return;
        
        this.editor.revealLineInCenter(line);
        this.editor.setPosition({
            lineNumber: line,
            column: column || 1
        });
        this.editor.focus();
    },
    
    /**
     * 更新状态栏
     * @param {Object} result - 验证结果
     */
    updateStatusBar(result) {
        const statusBar = document.getElementById('status-bar');
        if (!statusBar) return;
        
        const syntaxStatus = statusBar.querySelector('.syntax-status');
        if (!syntaxStatus) return;
        
        // 非HPL文件，显示跳过状态
        if (result.isNonHPL) {
            syntaxStatus.innerHTML = '⏭️ 非HPL文件';
            syntaxStatus.className = 'syntax-status skipped';
            return;
        }
        
        const errorCount = result.total_errors || 0;
        const warningCount = result.total_warnings || 0;
        
        if (errorCount === 0 && warningCount === 0) {
            syntaxStatus.innerHTML = '✅ 语法正确';
            syntaxStatus.className = 'syntax-status valid';
        } else {
            const parts = [];
            if (errorCount > 0) parts.push(`${errorCount} 个错误`);
            if (warningCount > 0) parts.push(`${warningCount} 个警告`);
            
            syntaxStatus.innerHTML = `❌ ${parts.join(', ')}`;
            syntaxStatus.className = 'syntax-status invalid';
        }
    },

    
    /**
     * 手动触发语法检查
     */
    manualCheck() {
        this.checkSyntax();
    },
    
    /**
     * 切换自动检查
     * @param {boolean} enabled - 是否启用
     */
    setAutoCheck(enabled) {
        this.config.autoCheck = enabled;
        
        if (enabled) {
            this.checkSyntax();
        }
    },
    
    /**
     * 获取当前配置
     * @returns {Object} 配置对象
     */
    getConfig() {
        return { ...this.config };
    },
    
    /**
     * 更新配置
     * @param {Object} newConfig - 新配置
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        
        // 如果启用了自动检查，立即执行一次
        if (this.config.autoCheck) {
            this.checkSyntax();
        }
    },
    
    /**
     * 获取当前标记列表
     * @returns {Array} 标记数组
     */
    getCurrentMarkers() {
        return [...this.state.currentMarkers];
    },
    
    /**
     * 检查当前是否存在错误
     * @returns {boolean} 是否存在错误
     */
    hasErrors() {
        return this.state.currentMarkers.some(m => m.severity === monaco.MarkerSeverity.Error);
    },
    
    /**
     * 获取错误统计信息
     * @returns {Object} 包含错误和警告数量的对象
     */
    getErrorStats() {
        const errors = this.state.currentMarkers.filter(m => m.severity === monaco.MarkerSeverity.Error).length;
        const warnings = this.state.currentMarkers.filter(m => m.severity === monaco.MarkerSeverity.Warning).length;
        return { errors, warnings, total: errors + warnings };
    },
    
    /**
     * 销毁诊断模块
     */
    dispose() {

        if (this.state.pendingCheck) {
            clearTimeout(this.state.pendingCheck);
        }
        
        this.clearDiagnostics();
        this.editor = null;
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { HPLDiagnostics };
}
