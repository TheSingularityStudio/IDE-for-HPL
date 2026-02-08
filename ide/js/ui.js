/**
 * HPL IDE - UI 工具模块
 * 管理界面交互、对话框、输出面板等
 */

const HPLUI = {
    // 状态指示器原始文本缓存
    _originalStatusText: '',
    
    // 当前输出过滤器
    _currentFilter: 'all',
    
    // 输出历史记录
    _outputHistory: [],

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
        
        // 同时更新面包屑导航
        this.updateBreadcrumb(filename);
    },

    /**
     * 更新面包屑导航
     */
    updateBreadcrumb(filename) {
        const breadcrumbContent = document.getElementById('breadcrumb-content');
        if (!breadcrumbContent) return;
        
        // 清空现有内容
        breadcrumbContent.innerHTML = '';
        
        // 添加根节点
        const rootItem = document.createElement('span');
        rootItem.className = 'breadcrumb-item root';
        rootItem.textContent = '📁 HPL IDE';
        rootItem.addEventListener('click', () => {
            HPLUI.showWelcomePage();
        });
        breadcrumbContent.appendChild(rootItem);
        
        if (!filename || filename === '未选择文件') {
            return;
        }
        
        // 解析文件路径
        const pathParts = filename.split('/');
        let currentPath = '';
        
        pathParts.forEach((part, index) => {
            // 添加分隔符
            const separator = document.createElement('span');
            separator.className = 'breadcrumb-separator';
            separator.textContent = '›';
            breadcrumbContent.appendChild(separator);
            
            // 构建当前路径
            currentPath = currentPath ? `${currentPath}/${part}` : part;
            
            // 创建路径项
            const item = document.createElement('span');
            item.className = 'breadcrumb-item';
            if (index === pathParts.length - 1) {
                item.classList.add('active');
            }
            item.textContent = part;
            item.dataset.path = currentPath;
            
            // 添加点击事件
            item.addEventListener('click', () => {
                // 如果是文件，打开它
                if (index === pathParts.length - 1 && HPLFileManager.openFiles.has(filename)) {
                    HPLFileManager.switchToFile(filename);
                } else {
                    // 如果是文件夹，可以展开/折叠
                    HPLUI.showOutput(`📂 导航到: ${currentPath}`, 'info');
                }
            });
            
            breadcrumbContent.appendChild(item);
        });
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
        
        // 存储到历史记录
        this._outputHistory.push({ message, type, timestamp: Date.now() });
        
        // 检查是否需要过滤
        if (this._currentFilter !== 'all' && this._currentFilter !== type) {
            line.classList.add('filtered');
        }
        
        // 如果是错误消息，添加可点击的链接
        if (type === 'error' && message.includes('行')) {
            const lineMatch = message.match(/第\s*(\d+)\s*行/);
            if (lineMatch) {
                const lineNum = parseInt(lineMatch[1]);
                line.innerHTML = this._createErrorLink(message, lineNum);
            }
        }
        
        outputContent.appendChild(line);
        outputContent.scrollTop = outputContent.scrollHeight;
    },

    /**
     * 创建可点击的错误链接
     */
    _createErrorLink(message, lineNum) {
        return message.replace(
            /第\s*(\d+)\s*行/,
            `第 <span class="error-link" onclick="HPLEditor.goToLine(${lineNum})" title="点击跳转到第 ${lineNum} 行">${lineNum}</span> 行`
        );
    },

    /**
     * 设置输出过滤器
     */
    setOutputFilter(filter) {
        this._currentFilter = filter;
        
        // 更新按钮状态
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });
        
        // 应用过滤
        const outputContent = document.getElementById('output-content');
        if (!outputContent) return;
        
        outputContent.querySelectorAll('.output-line').forEach(line => {
            const lineType = line.className.match(/output-(\w+)/)?.[1] || 'normal';
            if (filter === 'all' || lineType === filter) {
                line.classList.remove('filtered');
            } else {
                line.classList.add('filtered');
            }
        });
    },

    /**
     * 清除输出
     */
    clearOutput() {
        if (confirm('确定要清空所有输出内容吗？')) {
            const outputContent = document.getElementById('output-content');
            if (outputContent) {
                outputContent.innerHTML = '';
            }
            this._outputHistory = [];
        }
    },

    /**
     * 显示自动保存指示器
     */
    showAutoSaveIndicator() {
        const fileInfo = document.getElementById('file-info');
        if (fileInfo && !fileInfo.textContent.includes('💾')) {
            fileInfo.textContent += ' 💾';
        }
    },

    /**
     * 显示保存对话框
     */
    showSaveDialog(defaultFilename) {
        const dialog = document.getElementById('save-dialog');
        const filenameInput = document.getElementById('save-filename');
        
        if (dialog && filenameInput) {
            filenameInput.value = defaultFilename || 'untitled.hpl';
            dialog.classList.remove('hidden');
            filenameInput.focus();
            filenameInput.select();
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
        const dialog = document.getElementById('config-dialog');
        const apiUrlInput = document.getElementById('config-api-url');
        const timeoutInput = document.getElementById('config-timeout');
        const fontSizeInput = document.getElementById('config-font-size');
        const themeInput = document.getElementById('config-theme');
        const autoSaveInput = document.getElementById('config-auto-save');
        
        if (dialog) {
            if (apiUrlInput) apiUrlInput.value = config.apiBaseUrl || '';
            if (timeoutInput) timeoutInput.value = config.requestTimeout || 7000;
            if (fontSizeInput) fontSizeInput.value = config.fontSize || 14;
            if (themeInput) themeInput.value = config.editorTheme || 'vs-dark';
            if (autoSaveInput) autoSaveInput.checked = config.autoSave || false;
            
            dialog.classList.remove('hidden');
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
     * 显示快捷键帮助对话框
     */
    showShortcutsDialog() {
        const dialog = document.getElementById('shortcuts-dialog');
        if (dialog) {
            dialog.classList.remove('hidden');
        }
    },

    /**
     * 隐藏快捷键帮助对话框
     */
    hideShortcutsDialog() {
        const dialog = document.getElementById('shortcuts-dialog');
        if (dialog) {
            dialog.classList.add('hidden');
        }
    },

    /**
     * 切换面板
     */
    switchPanel(panelName) {
        // 更新标签页状态
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.panel === panelName);
        });
        
        // 显示/隐藏面板内容
        document.querySelectorAll('.panel-content > div').forEach(panel => {
            panel.classList.toggle('hidden', !panel.id.startsWith(panelName));
        });
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
        
        // 重置面包屑
        this.updateBreadcrumb(null);
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
