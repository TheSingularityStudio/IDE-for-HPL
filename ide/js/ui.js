/**
 * HPL IDE - UI 工具模块
 * 管理界面交互、对话框、输出面板等
 */

const HPLUI = {
    // 状态指示器原始文本缓存
    _originalStatusText: '',

    /**
     * 显示加载指示器
     */
    showLoading(message = '加载中...') {
        const statusIndicator = document.getElementById('status-indicator');
        if (statusIndicator) {
            this._originalStatusText = statusIndicator.textContent;
            statusIndicator.textContent = `⏳ ${message}`;
            statusIndicator.className = 'status-running';
        }
    },

    /**
     * 隐藏加载指示器
     */
    hideLoading() {
        const statusIndicator = document.getElementById('status-indicator');
        if (statusIndicator && this._originalStatusText) {
            statusIndicator.textContent = this._originalStatusText;
            statusIndicator.className = 'status-ready';
        }
    },

    /**
     * 更新状态栏文件信息
     */
    updateFileInfo(filename, isModified = false) {
        const fileInfo = document.getElementById('file-info');
        if (fileInfo) {
            fileInfo.textContent = isModified ? `${filename}*` : filename;
        }
    },

    /**
     * 更新光标位置信息
     */
    updateCursorInfo(lineNumber, column) {
        const cursorInfo = document.getElementById('cursor-info');
        if (cursorInfo) {
            cursorInfo.textContent = `行 ${lineNumber}, 列 ${column}`;
        }
    },

    /**
     * 显示输出消息
     */
    showOutput(message, type = 'normal') {
        const outputContent = document.getElementById('output-content');
        if (!outputContent) return;
        
        const line = document.createElement('div');
        line.className = `output-line output-${type}`;
        line.textContent = message;
        outputContent.appendChild(line);
        outputContent.scrollTop = outputContent.scrollHeight;
    },

    /**
     * 清空输出面板
     */
    clearOutput() {
        const outputContent = document.getElementById('output-content');
        if (outputContent) {
            outputContent.innerHTML = '';
        }
    },

    /**
     * 切换底部面板
     */
    switchPanel(panelName) {
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.panel === panelName);
        });
        
        const outputPanel = document.getElementById('output-panel');
        const problemsPanel = document.getElementById('problems-panel');
        
        if (outputPanel) {
            outputPanel.classList.toggle('hidden', panelName !== 'output');
        }
        if (problemsPanel) {
            problemsPanel.classList.toggle('hidden', panelName !== 'problems');
        }
    },

    /**
     * 显示保存对话框
     */
    showSaveDialog(defaultFilename = 'untitled.hpl') {
        const dialog = document.getElementById('save-dialog');
        const filenameInput = document.getElementById('save-filename');
        if (dialog && filenameInput) {
            dialog.classList.remove('hidden');
            filenameInput.value = defaultFilename;
            filenameInput.focus();
        }
    },

    /**
     * 隐藏保存对话框
     */
    hideSaveDialog() {
        const dialog = document.getElementById('save-dialog');
        if (dialog) {
            dialog.classList.add('hidden');
        }
    },

    /**
     * 显示配置对话框
     */
    showConfigDialog(config) {
        try {
            const apiUrlInput = document.getElementById('config-api-url');
            const timeoutInput = document.getElementById('config-timeout');
            const fontSizeInput = document.getElementById('config-font-size');
            const themeInput = document.getElementById('config-theme');
            const autoSaveInput = document.getElementById('config-auto-save');
            const dialog = document.getElementById('config-dialog');
            
            if (apiUrlInput) apiUrlInput.value = config.apiBaseUrl;
            if (timeoutInput) timeoutInput.value = config.requestTimeout;
            if (fontSizeInput) fontSizeInput.value = config.fontSize;
            if (themeInput) themeInput.value = config.editorTheme;
            if (autoSaveInput) autoSaveInput.checked = config.autoSave;
            if (dialog) dialog.classList.remove('hidden');
        } catch (error) {
            console.error('显示配置对话框失败:', error);
            this.showOutput('无法显示配置对话框', 'error');
        }
    },

    /**
     * 隐藏配置对话框
     */
    hideConfigDialog() {
        const dialog = document.getElementById('config-dialog');
        if (dialog) {
            dialog.classList.add('hidden');
        }
    },

    /**
     * 显示自动保存指示器
     */
    showAutoSaveIndicator() {
        const fileInfo = document.getElementById('file-info');
        if (!fileInfo) return;
        
        const originalText = fileInfo.textContent;
        fileInfo.textContent = originalText + ' (已自动保存)';
        fileInfo.style.color = 'var(--success-color)';
        
        setTimeout(() => {
            fileInfo.textContent = originalText;
            fileInfo.style.color = '';
        }, 2000);
    },

    /**
     * 创建标签页元素
     */
    createTabElement(filename, displayName) {
        const tab = document.createElement('div');
        tab.className = 'tab';
        tab.dataset.file = filename;
        
        const iconSpan = document.createElement('span');
        iconSpan.className = 'tab-icon';
        iconSpan.textContent = '📄';
        
        const titleSpan = document.createElement('span');
        titleSpan.className = 'tab-title';
        titleSpan.textContent = displayName;
        
        const closeSpan = document.createElement('span');
        closeSpan.className = 'tab-close';
        closeSpan.textContent = '×';
        
        tab.appendChild(iconSpan);
        tab.appendChild(titleSpan);
        tab.appendChild(closeSpan);
        
        return tab;
    },

    /**
     * 更新标签页标题
     */
    updateTabTitle(filename, isModified) {
        const tab = document.querySelector(`.tab[data-file="${HPLUtils.escapeHtml(filename)}"]`);
        if (tab) {
            const titleSpan = tab.querySelector('.tab-title');
            if (titleSpan) {
                titleSpan.textContent = isModified ? filename + '*' : filename;
            }
        }
    },

    /**
     * 移除标签页
     */
    removeTab(filename) {
        const tab = document.querySelector(`.tab[data-file="${HPLUtils.escapeHtml(filename)}"]`);
        if (tab) {
            tab.remove();
        }
    },

    /**
     * 切换标签页激活状态
     */
    switchTab(filename) {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.file === filename);
        });
    },

    /**
     * 显示欢迎页面
     */
    showWelcomePage() {
        const welcomePage = document.getElementById('welcome-page');
        if (welcomePage) {
            welcomePage.style.display = 'flex';
        }
    },

    /**
     * 隐藏欢迎页面
     */
    hideWelcomePage() {
        const welcomePage = document.getElementById('welcome-page');
        if (welcomePage) {
            welcomePage.style.display = 'none';
        }
    },

    /**
     * 更新运行按钮状态
     */
    updateRunButtonState(isRunning) {
        const runBtn = document.getElementById('btn-run');
        const statusIndicator = document.getElementById('status-indicator');
        
        if (runBtn) {
            runBtn.disabled = isRunning;
        }
        
        if (statusIndicator) {
            if (isRunning) {
                statusIndicator.textContent = '运行中...';
                statusIndicator.className = 'status-running';
            } else {
                statusIndicator.textContent = '就绪';
                statusIndicator.className = 'status-ready';
            }
        }
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLUI;
}
