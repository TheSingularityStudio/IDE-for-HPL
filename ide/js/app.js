/**
 * HPL IDE - 主应用入口
 * 协调各模块，处理事件绑定和初始化
 */

// 应用状态
const HPLApp = {
    isRunning: false,

    /**
     * 初始化应用
     */
    async init() {
        console.log('HPL IDE 初始化开始...');
        
        try {
            // 初始化编辑器
            await HPLEditor.init();
            
            // 初始化文件管理器
            HPLFileManager.init();
            
            // 绑定事件
            this.bindEvents();
            
            // 刷新文件树
            this.refreshFileTree();
            
            console.log('HPL IDE 初始化完成');
        } catch (error) {
            console.error('HPL IDE 初始化失败:', error);
            HPLUI.showOutput('初始化失败: ' + error.message, 'error');
        }
    },

    /**
     * 绑定所有事件
     */
    bindEvents() {
        this.bindToolbarEvents();
        this.bindDialogEvents();
        this.bindPanelEvents();
        this.bindKeyboardEvents();
        this.bindFileTreeEvents();
        this.bindWelcomePageEvents();
    },

    /**
     * 绑定工具栏事件
     */
    bindToolbarEvents() {
        const btnNew = document.getElementById('btn-new');
        const btnOpen = document.getElementById('btn-open');
        const btnSave = document.getElementById('btn-save');
        const btnRun = document.getElementById('btn-run');
        const btnRefresh = document.getElementById('btn-refresh');
        const btnClearOutput = document.getElementById('btn-clear-output');
        const btnConfig = document.getElementById('btn-config');
        const fileInput = document.getElementById('file-input');

        if (btnNew) btnNew.addEventListener('click', () => HPLFileManager.newFile());
        if (btnOpen) btnOpen.addEventListener('click', () => fileInput?.click());
        if (btnSave) btnSave.addEventListener('click', () => HPLFileManager.saveCurrentFile());
        if (btnRun) btnRun.addEventListener('click', () => this.runCode());
        if (btnRefresh) btnRefresh.addEventListener('click', () => this.refreshFileTree());
        if (btnClearOutput) btnClearOutput.addEventListener('click', () => HPLUI.clearOutput());
        if (btnConfig) btnConfig.addEventListener('click', () => this.showConfigDialog());
        
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    HPLFileManager.openFromFileInput(file);
                }
                // 重置 input
                e.target.value = '';
            });
        }
    },

    /**
     * 绑定对话框事件
     */
    bindDialogEvents() {
        // 保存对话框
        const btnSaveConfirm = document.getElementById('btn-save-confirm');
        const btnSaveCancel = document.getElementById('btn-save-cancel');
        const btnSaveClose = document.getElementById('btn-save-close');

        if (btnSaveConfirm) {
            btnSaveConfirm.addEventListener('click', () => {
                const filenameInput = document.getElementById('save-filename');
                const filename = filenameInput?.value?.trim();
                if (filename) {
                    HPLFileManager.confirmSave(filename);
                }
            });
        }
        if (btnSaveCancel) btnSaveCancel.addEventListener('click', () => HPLUI.hideSaveDialog());
        if (btnSaveClose) btnSaveClose.addEventListener('click', () => HPLUI.hideSaveDialog());

        // 配置对话框
        const btnConfigCancel = document.getElementById('btn-config-cancel');
        const btnConfigClose = document.getElementById('btn-config-close');
        const btnConfigSave = document.getElementById('btn-config-save');
        const btnConfigReset = document.getElementById('btn-config-reset');
        const btnTestConnection = document.getElementById('btn-test-connection');

        if (btnConfigCancel) btnConfigCancel.addEventListener('click', () => HPLUI.hideConfigDialog());
        if (btnConfigClose) btnConfigClose.addEventListener('click', () => HPLUI.hideConfigDialog());
        if (btnConfigSave) btnConfigSave.addEventListener('click', () => this.saveConfig());
        if (btnConfigReset) btnConfigReset.addEventListener('click', () => this.resetConfig());
        if (btnTestConnection) btnTestConnection.addEventListener('click', () => this.testConnection());
    },

    /**
     * 绑定面板事件
     */
    bindPanelEvents() {
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', () => HPLUI.switchPanel(tab.dataset.panel));
        });
    },

    /**
     * 绑定键盘快捷键
     */
    bindKeyboardEvents() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + 快捷键
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'n':
                        e.preventDefault();
                        HPLFileManager.newFile();
                        break;
                    case 'o':
                        e.preventDefault();
                        document.getElementById('file-input')?.click();
                        break;
                    case 's':
                        e.preventDefault();
                        HPLFileManager.saveCurrentFile();
                        break;
                    case ',':
                        if (!e.shiftKey) {
                            e.preventDefault();
                            this.showConfigDialog();
                        }
                        break;
                }
            } else if (e.key === 'F5') {
                // F5 运行
                e.preventDefault();
                this.runCode();
            } else if (e.key === 'Escape') {
                // ESC 关闭对话框
                HPLUI.hideSaveDialog();
                HPLUI.hideConfigDialog();
            }
        });
    },

    /**
     * 绑定文件树事件
     * 注意：主要事件处理已移至 HPLFileManager.initFileTreeEvents()
     * 这里保留一些额外的应用级别处理
     */
    bindFileTreeEvents() {
        // 文件树事件主要由 HPLFileManager 处理
        // 这里可以添加额外的应用级别事件
    },


    /**
     * 绑定欢迎页面事件
     */
    bindWelcomePageEvents() {
        const actionNew = document.getElementById('action-new');
        const actionOpen = document.getElementById('action-open');
        const actionExample = document.getElementById('action-example');

        if (actionNew) actionNew.addEventListener('click', () => HPLFileManager.newFile());
        if (actionOpen) actionOpen.addEventListener('click', () => document.getElementById('file-input')?.click());
        if (actionExample) actionExample.addEventListener('click', () => this.loadExample('example.hpl'));

        // 绑定欢迎标签页点击事件
        const welcomeTab = document.querySelector('.tab[data-file="welcome"]');
        if (welcomeTab) {
            welcomeTab.addEventListener('click', () => {
                // 清除所有标签页的激活状态
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                // 激活欢迎标签页
                welcomeTab.classList.add('active');
                // 显示欢迎页面
                HPLUI.showWelcomePage();
                // 清空当前文件状态
                HPLFileManager.currentFile = null;
                HPLUI.updateFileInfo('未选择文件', false);
            });
        }
    },


    /**
     * 运行代码
     */
    async runCode() {
        if (this.isRunning) return;
        
        const code = HPLEditor.getValue();
        if (!code.trim()) {
            HPLUI.showOutput('没有可运行的代码', 'error');
            return;
        }
        
        // 清除之前的错误高亮
        HPLEditor.clearErrorHighlights();
        
        this.isRunning = true;
        HPLUI.updateRunButtonState(true);
        HPLUI.showOutput('正在运行程序...\n', 'info');
        
        try {
            const result = await HPLAPI.runCode(code);
            
            if (result.success) {
                HPLUI.showOutput(result.output || '程序执行完成（无输出）', 'success');
            } else {
                // 显示错误信息
                let errorMsg = result.error || '未知错误';
                HPLUI.showOutput('错误: ' + errorMsg, 'error');
                
                // 如果有行号信息，高亮错误行
                if (result.line) {
                    const lineNum = parseInt(result.line);
                    const column = result.column ? parseInt(result.column) : 1;
                    HPLEditor.highlightErrorLine(lineNum, column);
                    
                    if (result.type === 'syntax_error') {
                        HPLUI.showOutput(`语法错误位于第 ${lineNum} 行${result.column ? `, 第 ${result.column} 列` : ''}`, 'error');
                    }
                }
                
                if (result.hint) {
                    HPLUI.showOutput('提示: ' + result.hint, 'info');
                }
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                HPLUI.showOutput('⏱️ 请求超时，请检查服务器状态或增加超时时间', 'error');
            } else {
                HPLUI.showOutput('无法连接到 HPL 运行时服务器。\n请确保后端服务器已启动 (python ide/server.py)\n\n错误: ' + error.message, 'error');
            }
        } finally {
            this.isRunning = false;
            HPLUI.updateRunButtonState(false);
        }
    },

    /**
     * 刷新文件树
     */
    async refreshFileTree() {
        const fileTree = document.getElementById('file-tree');
        if (!fileTree) return;
        
        HPLUI.showLoading('刷新文件列表...');
        fileTree.innerHTML = '<div class="file-item loading">⏳ 加载中...</div>';
        
        try {
            // 使用新的文件树 API
            const treeData = await HPLAPI.getFileTree();
            
            // 设置文件树数据并渲染
            HPLFileManager.setFileTreeData(treeData);
            
            console.log('文件树已刷新');
            HPLUI.hideLoading();
        } catch (error) {
            console.error('刷新文件树失败:', error);
            // 如果新 API 失败，回退到旧 API
            try {
                const examples = await HPLAPI.listExamples();
                const treeData = {
                    name: 'examples',
                    path: 'examples',
                    type: 'folder',
                    children: examples.map(ex => ({
                        name: ex.name,
                        path: `examples/${ex.name}`,
                        type: 'file',
                        size: ex.size
                    }))
                };
                HPLFileManager.setFileTreeData(treeData);
                HPLUI.hideLoading();
            } catch (fallbackError) {
                fileTree.innerHTML = `<div class="file-item error">❌ 加载失败: ${HPLUtils.escapeHtml(error.message)}</div>`;
                HPLUI.showOutput('刷新文件树失败: ' + error.message, 'error');
                HPLUI.hideLoading();
            }
        }
    },


    /**
     * 加载示例文件
     */
    async loadExample(filename) {
        HPLUI.showOutput(`正在加载 ${filename}...`, 'info');
        
        try {
            const result = await HPLAPI.loadExample(filename);
            HPLFileManager.openFileInEditor(filename, result.content, false);
            
            // 在文件树中高亮该文件
            HPLFileManager.highlightFileInTree(filename);
            
            HPLUI.showOutput(`✅ 已加载: ${filename}`, 'success');
        } catch (error) {
            HPLUI.showOutput('无法加载示例文件: ' + error.message, 'error');
        }
    },


    /**
     * 显示配置对话框
     */
    showConfigDialog() {
        const config = HPLConfig.getConfig();
        HPLUI.showConfigDialog(config);
    },

    /**
     * 保存配置
     */
    saveConfig() {
        const apiUrlInput = document.getElementById('config-api-url');
        const timeoutInput = document.getElementById('config-timeout');
        const fontSizeInput = document.getElementById('config-font-size');
        const themeInput = document.getElementById('config-theme');
        const autoSaveInput = document.getElementById('config-auto-save');
        
        const apiUrl = apiUrlInput?.value?.trim();
        const timeout = parseInt(timeoutInput?.value) || 7000;
        const fontSize = parseInt(fontSizeInput?.value) || 14;
        const theme = themeInput?.value || 'vs-dark';
        const autoSave = autoSaveInput?.checked || false;
        
        if (!apiUrl) {
            HPLUI.showOutput('错误: API 地址不能为空', 'error');
            return;
        }
        
        try {
            new URL(apiUrl);
        } catch (e) {
            HPLUI.showOutput('错误: API 地址格式不正确', 'error');
            return;
        }
        
        try {
            HPLConfig.saveConfig({
                apiBaseUrl: apiUrl,
                requestTimeout: timeout,
                fontSize: fontSize,
                editorTheme: theme,
                autoSave: autoSave
            });
            
            // 应用字体大小
            HPLEditor.updateOptions({ fontSize: fontSize });
            
            // 应用主题
            HPLEditor.setTheme(theme);
            
            // 重新初始化自动保存
            HPLFileManager.initAutoSave();
            
            HPLUI.hideConfigDialog();
            HPLUI.showOutput('配置已保存', 'success');
        } catch (error) {
            HPLUI.showOutput('保存配置失败: ' + error.message, 'error');
        }
    },

    /**
     * 重置配置
     */
    resetConfig() {
        try {
            HPLConfig.resetConfig();
            const config = HPLConfig.getConfig();
            
            // 更新对话框中的值
            const apiUrlInput = document.getElementById('config-api-url');
            const timeoutInput = document.getElementById('config-timeout');
            const fontSizeInput = document.getElementById('config-font-size');
            const themeInput = document.getElementById('config-theme');
            const autoSaveInput = document.getElementById('config-auto-save');
            
            if (apiUrlInput) apiUrlInput.value = config.apiBaseUrl;
            if (timeoutInput) timeoutInput.value = config.requestTimeout;
            if (fontSizeInput) fontSizeInput.value = config.fontSize;
            if (themeInput) themeInput.value = config.editorTheme;
            if (autoSaveInput) autoSaveInput.checked = config.autoSave;
            
            // 重新初始化自动保存
            HPLFileManager.initAutoSave();
            
            HPLUI.showOutput('配置已重置为默认值', 'info');
        } catch (error) {
            HPLUI.showOutput('重置配置失败: ' + error.message, 'error');
        }
    },

    /**
     * 测试服务器连接
     */
    async testConnection() {
        const btn = document.getElementById('btn-test-connection');
        if (!btn) return;
        
        const originalText = btn.textContent;
        btn.textContent = '⏳ 测试中...';
        btn.disabled = true;
        
        try {
            const result = await HPLAPI.testConnection();
            
            if (result.success) {
                HPLUI.showOutput('✅ 连接成功！服务器运行正常', 'success');
            } else {
                HPLUI.showOutput('❌ 连接失败: ' + result.error, 'error');
            }
        } catch (error) {
            HPLUI.showOutput('❌ 连接测试出错: ' + error.message, 'error');
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }
};

// DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    HPLApp.init();
});
