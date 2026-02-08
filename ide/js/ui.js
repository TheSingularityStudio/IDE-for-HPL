/**
 * HPL IDE - UI 工具模块
 * 管理界面交互、对话框、输出面板等
 */

const HPLUI = {
    // 状态指示器原始文本缓存
    _originalStatusText: '',
    
    // 面板状态管理
    _panelState: {
        height: 200,        // 当前高度
        isMaximized: false, // 是否最大化
        isMinimized: false, // 是否最小化
        isClosed: false,    // 是否关闭
        previousHeight: 200 // 恢复时使用的高度
    },


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
     * 切换底部面板标签
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
        
        // 如果面板是关闭状态，先展开它
        if (this._panelState.isClosed) {
            this.restorePanel();
        }
    },

    /**
     * 初始化面板管理
     */
    initPanelManager() {
        this._initPanelResizer();
        this._loadPanelState();
    },

    /**
     * 初始化面板拖拽调整大小功能
     */
    _initPanelResizer() {
        const resizer = document.getElementById('panel-resizer');
        const bottomPanel = document.getElementById('bottom-panel');
        
        if (!resizer || !bottomPanel) return;
        
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;
        
        // 鼠标按下开始拖拽
        resizer.addEventListener('mousedown', (e) => {
            if (this._panelState.isMaximized || this._panelState.isMinimized) {
                return; // 最大化或最小化状态下不允许拖拽
            }
            
            isResizing = true;
            startY = e.clientY;
            startHeight = bottomPanel.offsetHeight;
            
            resizer.classList.add('resizing');
            document.body.style.cursor = 'row-resize';
            document.body.style.userSelect = 'none';
            
            e.preventDefault();
        });
        
        // 鼠标移动时调整高度
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            
            const deltaY = startY - e.clientY;
            const newHeight = Math.max(100, Math.min(600, startHeight + deltaY));
            
            bottomPanel.style.height = `${newHeight}px`;
            this._panelState.height = newHeight;
        });
        
        // 鼠标释放结束拖拽
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                resizer.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                
                // 保存状态
                this._savePanelState();
            }
        });
    },

    /**
     * 最大化面板
     */
    maximizePanel() {
        const bottomPanel = document.getElementById('bottom-panel');
        const btnMaximize = document.getElementById('btn-panel-maximize');
        
        if (!bottomPanel) return;
        
        if (this._panelState.isMaximized) {
            // 如果已经最大化，则恢复
            this.restorePanel();
            return;
        }
        
        // 保存当前高度
        this._panelState.previousHeight = this._panelState.height;
        
        // 应用最大化样式
        bottomPanel.classList.add('maximized');
        bottomPanel.classList.remove('minimized');
        bottomPanel.style.height = '';
        
        this._panelState.isMaximized = true;
        this._panelState.isMinimized = false;
        this._panelState.isClosed = false;
        
        // 更新按钮图标
        if (btnMaximize) {
            btnMaximize.innerHTML = '⬇️';
            btnMaximize.title = '恢复面板';
        }
        
        // 隐藏折叠指示器
        this._hideCollapsedIndicator();
        
        this._savePanelState();
    },

    /**
     * 最小化面板
     */
    minimizePanel() {
        const bottomPanel = document.getElementById('bottom-panel');
        const btnMaximize = document.getElementById('btn-panel-maximize');
        
        if (!bottomPanel) return;
        
        // 保存当前高度（如果不是最大化状态）
        if (!this._panelState.isMaximized) {
            this._panelState.previousHeight = this._panelState.height;
        }
        
        // 应用最小化样式
        bottomPanel.classList.add('minimized');
        bottomPanel.classList.remove('maximized');
        bottomPanel.style.height = '';
        
        this._panelState.isMinimized = true;
        this._panelState.isMaximized = false;
        this._panelState.isClosed = false;
        
        // 更新按钮图标
        if (btnMaximize) {
            btnMaximize.innerHTML = '⬆️';
            btnMaximize.title = '恢复面板';
        }
        
        // 显示折叠指示器
        this._showCollapsedIndicator();
        
        this._savePanelState();
    },

    /**
     * 关闭面板
     */
    closePanel() {
        const bottomPanel = document.getElementById('bottom-panel');
        
        if (!bottomPanel) return;
        
        // 保存当前高度
        if (!this._panelState.isMaximized && !this._panelState.isMinimized) {
            this._panelState.previousHeight = this._panelState.height;
        }
        
        // 应用关闭样式（完全隐藏）
        bottomPanel.style.height = '0px';
        bottomPanel.style.overflow = 'hidden';
        bottomPanel.style.borderTop = 'none';
        
        this._panelState.isClosed = true;
        this._panelState.isMaximized = false;
        this._panelState.isMinimized = false;
        
        // 显示折叠指示器
        this._showCollapsedIndicator();
        
        this._savePanelState();
    },

    /**
     * 恢复面板到正常状态
     */
    restorePanel() {
        const bottomPanel = document.getElementById('bottom-panel');
        const btnMaximize = document.getElementById('btn-panel-maximize');
        const resizer = document.getElementById('panel-resizer');
        
        if (!bottomPanel) return;
        
        // 移除所有特殊状态样式
        bottomPanel.classList.remove('maximized', 'minimized');
        bottomPanel.style.overflow = '';
        bottomPanel.style.borderTop = '';
        
        // 恢复高度
        const restoreHeight = this._panelState.previousHeight || 200;
        bottomPanel.style.height = `${restoreHeight}px`;
        this._panelState.height = restoreHeight;
        
        this._panelState.isMaximized = false;
        this._panelState.isMinimized = false;
        this._panelState.isClosed = false;
        
        // 更新按钮图标
        if (btnMaximize) {
            btnMaximize.innerHTML = '⬆️';
            btnMaximize.title = '最大化面板';
        }
        
        // 隐藏折叠指示器
        this._hideCollapsedIndicator();
        
        // 显示调整手柄
        if (resizer) {
            resizer.style.display = '';
        }
        
        this._savePanelState();
    },

    /**
     * 切换面板显示/隐藏
     */
    togglePanel() {
        if (this._panelState.isClosed || this._panelState.isMinimized) {
            this.restorePanel();
        } else {
            this.minimizePanel();
        }
    },

    /**
     * 显示折叠指示器
     */
    _showCollapsedIndicator() {
        const indicator = document.getElementById('panel-collapsed-indicator');
        if (indicator) {
            indicator.classList.remove('hidden');
        }
    },

    /**
     * 隐藏折叠指示器
     */
    _hideCollapsedIndicator() {
        const indicator = document.getElementById('panel-collapsed-indicator');
        if (indicator) {
            indicator.classList.add('hidden');
        }
    },

    /**
     * 保存面板状态到 localStorage
     */
    _savePanelState() {
        try {
            localStorage.setItem('hpl_panel_state', JSON.stringify(this._panelState));
        } catch (e) {
            console.warn('无法保存面板状态:', e);
        }
    },

    /**
     * 从 localStorage 加载面板状态
     */
    _loadPanelState() {
        try {
            const saved = localStorage.getItem('hpl_panel_state');
            if (saved) {
                const state = JSON.parse(saved);
                this._panelState = { ...this._panelState, ...state };
                
                // 应用保存的状态
                const bottomPanel = document.getElementById('bottom-panel');
                if (bottomPanel) {
                    if (this._panelState.isMaximized) {
                        this.maximizePanel();
                    } else if (this._panelState.isMinimized) {
                        this.minimizePanel();
                    } else if (this._panelState.isClosed) {
                        this.closePanel();
                    } else {
                        bottomPanel.style.height = `${this._panelState.height}px`;
                    }
                }
            }
        } catch (e) {
            console.warn('无法加载面板状态:', e);
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
