/**
 * HPL IDE - 主应用程序
 * 集成 Monaco Editor，提供 HPL 语言支持
 */

// 配置常量
const CONFIG = {
    MONACO_VERSION: '0.44.0',
    DEFAULT_FILENAME: 'untitled.hpl',
    DEFAULT_FONT_SIZE: 14,
    DEFAULT_TIMEOUT: 30000
};

// 使用命名空间封装全局变量，避免污染全局作用域
const HPLIDE = {
    editor: null,
    currentFile: null,
    openFiles: new Map(),
    isRunning: false
};

// 获取编辑器实例的快捷方式
const getEditor = () => HPLIDE.editor;
const getCurrentFile = () => HPLIDE.currentFile;
const getOpenFiles = () => HPLIDE.openFiles;
const getIsRunning = () => HPLIDE.isRunning;
const setIsRunning = (value) => { HPLIDE.isRunning = value; };

// HPL 自动补全提供程序
const hplCompletionProvider = {
    provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: word.startColumn,
            endColumn: word.endColumn
        };

        const suggestions = [
            // 关键字
            { label: 'includes', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'includes:\n  - ', documentation: '包含其他 HPL 文件', range },
            { label: 'classes', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'classes:\n  ClassName:\n    method: () => {\n        \n      }', documentation: '定义类', range },
            { label: 'objects', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'objects:\n  objectName: ClassName()', documentation: '实例化对象', range },
            { label: 'main', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'main: () => {\n    \n  }', documentation: '主函数', range },
            { label: 'call', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'call: main()', documentation: '调用主函数', range },
            { label: 'imports', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'imports:\n  - ', documentation: '导入标准库模块', range },
            { label: 'parent', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'parent: BaseClass', documentation: '指定父类', range },
            
            // 控制流
            { label: 'if', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'if (condition) :\n    ', documentation: '条件语句', range },
            { label: 'else', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'else :\n    ', documentation: 'else 分支', range },
            { label: 'for', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'for (i = 0; i < count; i++) :\n    ', documentation: 'for 循环', range },
            { label: 'while', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'while (condition) :\n    ', documentation: 'while 循环', range },
            { label: 'try', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'try :\n    ', documentation: 'try 块', range },
            { label: 'catch', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'catch (error) :\n    ', documentation: 'catch 块', range },
            { label: 'return', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'return ', documentation: '返回值', range },
            { label: 'break', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'break', documentation: '跳出循环', range },
            { label: 'continue', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'continue', documentation: '继续下一次循环', range },
            
            // 内置函数
            { label: 'echo', kind: monaco.languages.CompletionItemKind.Function, insertText: 'echo(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '输出值到控制台', range },
            { label: 'len', kind: monaco.languages.CompletionItemKind.Function, insertText: 'len(${1:array_or_string})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取数组或字符串长度', range },
            { label: 'int', kind: monaco.languages.CompletionItemKind.Function, insertText: 'int(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '转换为整数', range },
            { label: 'str', kind: monaco.languages.CompletionItemKind.Function, insertText: 'str(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '转换为字符串', range },
            { label: 'type', kind: monaco.languages.CompletionItemKind.Function, insertText: 'type(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取值类型', range },
            { label: 'abs', kind: monaco.languages.CompletionItemKind.Function, insertText: 'abs(${1:number})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取绝对值', range },
            { label: 'max', kind: monaco.languages.CompletionItemKind.Function, insertText: 'max(${1:a}, ${2:b})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取最大值', range },
            { label: 'min', kind: monaco.languages.CompletionItemKind.Function, insertText: 'min(${1:a}, ${2:b})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取最小值', range },
            
            // 标准库模块
            { label: 'math', kind: monaco.languages.CompletionItemKind.Module, insertText: 'math', documentation: '数学模块', range },
            { label: 'io', kind: monaco.languages.CompletionItemKind.Module, insertText: 'io', documentation: '文件IO模块', range },
            { label: 'json', kind: monaco.languages.CompletionItemKind.Module, insertText: 'json', documentation: 'JSON处理模块', range },
            { label: 'os', kind: monaco.languages.CompletionItemKind.Module, insertText: 'os', documentation: '操作系统接口模块', range },
            { label: 'time', kind: monaco.languages.CompletionItemKind.Module, insertText: 'time', documentation: '日期时间处理模块', range },
            
            // 布尔值
            { label: 'true', kind: monaco.languages.CompletionItemKind.Constant, insertText: 'true', documentation: '真', range },
            { label: 'false', kind: monaco.languages.CompletionItemKind.Constant, insertText: 'false', documentation: '假', range },
            
            // this
            { label: 'this', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'this', documentation: '当前对象引用', range },
        ];

        return { suggestions };
    }
};

// 安全的HTML转义函数，防止XSS攻击
function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 初始化 Monaco Editor
function initMonaco() {
    try {
        require.config({ paths: { 'vs': `https://cdn.jsdelivr.net/npm/monaco-editor@${CONFIG.MONACO_VERSION}/min/vs` }});

        require(['vs/editor/editor.main'], function() {
            try {
                // 注册 HPL 语言
                monaco.languages.register({ id: 'hpl' });
                
                // 设置语言配置
                monaco.languages.setLanguageConfiguration('hpl', {
                    comments: {
                        lineComment: '#'
                    },
                    brackets: [
                        ['{', '}'],
                        ['[', ']'],
                        ['(', ')']
                    ],
                    autoClosingPairs: [
                        { open: '{', close: '}' },
                        { open: '[', close: ']' },
                        { open: '(', close: ')' },
                        { open: '"', close: '"' }
                    ],
                    surroundingPairs: [
                        { open: '{', close: '}' },
                        { open: '[', close: ']' },
                        { open: '(', close: ')' },
                        { open: '"', close: '"' }
                    ]
                });

                // 设置 Token 提供程序
                monaco.languages.setMonarchTokensProvider('hpl', {
                    tokenizer: {
                        root: [
                            [/#.*$/, 'comment'],
                            [/"([^"\\]|\\.)*$/, 'string.invalid'],
                            [/"/, 'string', '@string'],
                            [/\b(includes|classes|objects|main|call|imports|parent|if|else|for|while|try|catch|return|break|continue)\b/, 'keyword'],
                            [/\b(echo|len|int|str|type|abs|max|min)\b/, 'predefined'],
                            [/\b(true|false)\b/, 'constant.boolean'],
                            [/\b\d+\.\d+\b/, 'number.float'],
                            [/\b\d+\b/, 'number'],
                            [/=>/, 'operator'],
                            [/[-+*/%=<>!&|]+/, 'operator'],
                            [/[a-zA-Z_]\w*/, 'identifier'],
                            [/[{}()\[\]]/, '@brackets'],
                            [/[;:,]/, 'delimiter'],
                            [/\s+/, 'white'],
                        ],
                        string: [
                            [/[^\\"]+/, 'string'],
                            [/\\./, 'string.escape'],
                            [/"/, 'string', '@pop']
                        ]
                    }
                });

                // 注册自动补全提供程序
                monaco.languages.registerCompletionItemProvider('hpl', hplCompletionProvider);

                // 创建编辑器
                HPLIDE.editor = monaco.editor.create(document.getElementById('editor'), {
                    value: '',
                    language: 'hpl',
                    theme: 'vs-dark',
                    automaticLayout: true,
                    minimap: { enabled: true },
                    fontSize: CONFIG.DEFAULT_FONT_SIZE,
                    fontFamily: 'Consolas, "Courier New", monospace',
                    lineNumbers: 'on',
                    roundedSelection: false,
                    scrollBeyondLastLine: false,
                    readOnly: false,
                    wordWrap: 'on',
                    folding: true,
                    renderWhitespace: 'selection',
                    matchBrackets: 'always',
                    autoIndent: 'full',
                    formatOnPaste: true,
                    formatOnType: true,
                    tabSize: 2,
                    insertSpaces: true,
                });

                // 监听光标位置变化
                HPLIDE.editor.onDidChangeCursorPosition((e) => {
                    const cursorInfo = document.getElementById('cursor-info');
                    if (cursorInfo) {
                        cursorInfo.textContent = `行 ${e.position.lineNumber}, 列 ${e.position.column}`;
                    }
                });

                // 监听内容变化
                HPLIDE.editor.onDidChangeModelContent(() => {
                    if (HPLIDE.currentFile) {
                        markFileAsModified(HPLIDE.currentFile, true);
                    }
                });
                
                console.log('Monaco Editor 初始化完成');

            } catch (error) {
                console.error('Monaco Editor 初始化失败:', error);
                showOutput('编辑器初始化失败: ' + error.message, 'error');
            }
        }, function(error) {
            // AMD 加载失败的回调
            console.error('加载 Monaco Editor 失败:', error);
            showOutput('加载编辑器失败，请检查网络连接', 'error');
        });
    } catch (error) {
        console.error('初始化 Monaco Editor 时发生错误:', error);
        showOutput('初始化失败: ' + error.message, 'error');
    }
}

// 文件操作
function newFile() {
    const filename = CONFIG.DEFAULT_FILENAME;
    const content = `classes:
  Main:
    main: () => {
        echo "Hello, HPL!"
      }

objects:
  app: Main()

main: () => {
    app.main()
  }

call: main()
`;
    
    openFileInEditor(filename, content, true);
}

function openFile() {
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.click();
    }
}

function handleFileOpen(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        openFileInEditor(file.name, e.target.result, false);
    };
    reader.onerror = (e) => {
        showOutput('读取文件失败: ' + (e.target.error?.message || '未知错误'), 'error');
    };
    reader.readAsText(file);
    
    // 重置 input
    event.target.value = '';
}

function saveFile() {
    if (!HPLIDE.currentFile) {
        showSaveDialog();
        return;
    }

    const editor = getEditor();
    if (!editor) return;

    const content = editor.getValue();
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    let a = null;
    try {
        a = document.createElement('a');
        a.href = url;
        a.download = HPLIDE.currentFile.replace('*', '');
        document.body.appendChild(a);
        a.click();
        
        markFileAsModified(HPLIDE.currentFile, false);
        showOutput('文件已保存: ' + HPLIDE.currentFile.replace('*', ''), 'success');
    } catch (error) {
        showOutput('保存文件失败: ' + error.message, 'error');
    } finally {
        // 确保资源被清理
        if (a && a.parentNode) {
            a.parentNode.removeChild(a);
        }
        URL.revokeObjectURL(url);
    }
}

function showSaveDialog() {
    const dialog = document.getElementById('save-dialog');
    const filenameInput = document.getElementById('save-filename');
    if (dialog && filenameInput) {
        dialog.classList.remove('hidden');
        filenameInput.value = CONFIG.DEFAULT_FILENAME;
        filenameInput.focus();
    }
}

function hideSaveDialog() {
    const dialog = document.getElementById('save-dialog');
    if (dialog) {
        dialog.classList.add('hidden');
    }
}

// 配置对话框
function showConfigDialog() {
    try {
        const config = HPLConfig.getConfig();
        const apiUrlInput = document.getElementById('config-api-url');
        const timeoutInput = document.getElementById('config-timeout');
        const fontSizeInput = document.getElementById('config-font-size');
        const themeInput = document.getElementById('config-theme');
        const dialog = document.getElementById('config-dialog');
        
        if (apiUrlInput) apiUrlInput.value = config.apiBaseUrl;
        if (timeoutInput) timeoutInput.value = config.requestTimeout;
        if (fontSizeInput) fontSizeInput.value = config.fontSize;
        if (themeInput) themeInput.value = config.editorTheme;
        if (dialog) dialog.classList.remove('hidden');
    } catch (error) {
        console.error('显示配置对话框失败:', error);
        showOutput('无法显示配置对话框', 'error');
    }
}

function hideConfigDialog() {
    const dialog = document.getElementById('config-dialog');
    if (dialog) {
        dialog.classList.add('hidden');
    }
}

async function testServerConnection() {
    const btn = document.getElementById('btn-test-connection');
    if (!btn) return;
    
    const originalText = btn.textContent;
    btn.textContent = '⏳ 测试中...';
    btn.disabled = true;
    
    try {
        const result = await HPLConfig.testConnection();
        
        if (result.success) {
            showOutput('✅ 连接成功！服务器运行正常', 'success');
        } else {
            showOutput('❌ 连接失败: ' + result.error, 'error');
        }
    } catch (error) {
        showOutput('❌ 连接测试出错: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

function saveConfig() {
    const apiUrlInput = document.getElementById('config-api-url');
    const timeoutInput = document.getElementById('config-timeout');
    const fontSizeInput = document.getElementById('config-font-size');
    const themeInput = document.getElementById('config-theme');
    
    const apiUrl = apiUrlInput?.value?.trim();
    const timeout = parseInt(timeoutInput?.value) || CONFIG.DEFAULT_TIMEOUT;
    const fontSize = parseInt(fontSizeInput?.value) || CONFIG.DEFAULT_FONT_SIZE;
    const theme = themeInput?.value || 'vs-dark';
    
    if (!apiUrl) {
        showOutput('错误: API 地址不能为空', 'error');
        return;
    }
    
    // 验证 API URL 格式
    try {
        new URL(apiUrl);
    } catch (e) {
        showOutput('错误: API 地址格式不正确', 'error');
        return;
    }
    
        try {
            HPLConfig.saveConfig({
                apiBaseUrl: apiUrl,
                requestTimeout: timeout,
                fontSize: fontSize,
                editorTheme: theme
            });
            
            // 应用字体大小
            const editor = getEditor();
            if (editor) {
                editor.updateOptions({ fontSize: fontSize });
            }
            
            // 应用主题
            if (theme && monaco && monaco.editor) {
                monaco.editor.setTheme(theme);
            }
            
            hideConfigDialog();
            showOutput('配置已保存', 'success');

    } catch (error) {
        showOutput('保存配置失败: ' + error.message, 'error');
    }
}

function resetConfig() {
    try {
        HPLConfig.resetConfig();
        const config = HPLConfig.getConfig();
        
        const apiUrlInput = document.getElementById('config-api-url');
        const timeoutInput = document.getElementById('config-timeout');
        const fontSizeInput = document.getElementById('config-font-size');
        const themeInput = document.getElementById('config-theme');
        
        if (apiUrlInput) apiUrlInput.value = config.apiBaseUrl;
        if (timeoutInput) timeoutInput.value = config.requestTimeout;
        if (fontSizeInput) fontSizeInput.value = config.fontSize;
        if (themeInput) themeInput.value = config.editorTheme;
        
        showOutput('配置已重置为默认值', 'info');
    } catch (error) {
        showOutput('重置配置失败: ' + error.message, 'error');
    }
}

// 验证文件名合法性
function isValidFilename(filename) {
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
}

function confirmSave() {
    const filenameInput = document.getElementById('save-filename');
    if (!filenameInput) return;
    
    const filename = filenameInput.value?.trim();
    
    if (!filename) {
        showOutput('错误: 文件名不能为空', 'error');
        return;
    }
    
    if (!isValidFilename(filename)) {
        showOutput('错误: 文件名包含非法字符或为系统保留名称', 'error');
        return;
    }
    
    // 确保文件名有扩展名
    const finalFilename = filename.endsWith('.hpl') ? filename : filename + '.hpl';
    
    const editor = getEditor();
    if (!editor) return;
    
    openFileInEditor(finalFilename, editor.getValue(), true);
    hideSaveDialog();
    saveFile();
}

// 在编辑器中打开文件
function openFileInEditor(filename, content, isNew = false) {
    // 检查是否已打开
    if (HPLIDE.openFiles.has(filename)) {
        switchToFile(filename);
        return;
    }

    const displayName = isNew ? filename + '*' : filename;
    HPLIDE.openFiles.set(filename, {
        content: content,
        isModified: isNew,
        isNew: isNew
    });

    // 创建标签页
    createTab(filename, displayName);
    
    // 切换到新文件
    switchToFile(filename);
    
    // 更新文件信息
    const fileInfo = document.getElementById('file-info');
    if (fileInfo) {
        fileInfo.textContent = filename;
    }
}

function createTab(filename, displayName) {
    const tabsContainer = document.getElementById('tabs-container');
    if (!tabsContainer) return;
    
    const tab = document.createElement('div');
    tab.className = 'tab';
    tab.dataset.file = filename;
    
    // 使用安全的DOM操作，避免XSS
    const iconSpan = document.createElement('span');
    iconSpan.className = 'tab-icon';
    iconSpan.textContent = '📄';
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'tab-title';
    titleSpan.textContent = displayName; // 使用 textContent 自动转义
    
    const closeSpan = document.createElement('span');
    closeSpan.className = 'tab-close';
    closeSpan.textContent = '×';
    
    tab.appendChild(iconSpan);
    tab.appendChild(titleSpan);
    tab.appendChild(closeSpan);
    
    // 点击切换
    tab.addEventListener('click', (e) => {
        if (e.target.classList.contains('tab-close')) {
            closeFile(filename);
        } else {
            switchToFile(filename);
        }
    });
    
    tabsContainer.appendChild(tab);
}

function switchToFile(filename) {
    // 更新标签页状态
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.file === filename);
    });
    
    const editor = getEditor();
    
    // 保存当前文件内容
    if (HPLIDE.currentFile && editor) {
        const fileData = HPLIDE.openFiles.get(HPLIDE.currentFile);
        if (fileData) {
            fileData.content = editor.getValue();
        }
    }
    
    // 切换文件
    HPLIDE.currentFile = filename;
    const fileData = HPLIDE.openFiles.get(filename);
    
    if (editor && fileData) {
        editor.setValue(fileData.content);
        editor.focus();
    }
    
    // 更新文件信息
    const fileInfo = document.getElementById('file-info');
    if (fileInfo) {
        fileInfo.textContent = fileData?.isModified ? filename + '*' : filename;
    }
    
    // 隐藏欢迎页面
    const welcomePage = document.getElementById('welcome-page');
    if (welcomePage) {
        welcomePage.style.display = 'none';
    }
}

function closeFile(filename) {
    const fileData = HPLIDE.openFiles.get(filename);
    
    // 如果有修改，提示保存
    if (fileData?.isModified) {
        if (!confirm(`文件 ${filename} 有未保存的更改，确定要关闭吗？`)) {
            return;
        }
    }
    
    HPLIDE.openFiles.delete(filename);
    
    // 移除标签页
    const tab = document.querySelector(`.tab[data-file="${escapeHtml(filename)}"]`);
    if (tab) {
        tab.remove();
    }
    
    // 如果关闭的是当前文件，切换到其他文件
    if (HPLIDE.currentFile === filename) {
        const remainingFiles = Array.from(HPLIDE.openFiles.keys());
        if (remainingFiles.length > 0) {
            switchToFile(remainingFiles[0]);
        } else {
            HPLIDE.currentFile = null;
            const editor = getEditor();
            if (editor) {
                editor.setValue('');
            }
            const welcomePage = document.getElementById('welcome-page');
            if (welcomePage) {
                welcomePage.style.display = 'flex';
            }
            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                fileInfo.textContent = '未选择文件';
            }
        }
    }
}

function markFileAsModified(filename, modified) {
    const fileData = HPLIDE.openFiles.get(filename);
    if (!fileData) return;
    
    fileData.isModified = modified;
    
    // 更新标签页标题
    const tab = document.querySelector(`.tab[data-file="${escapeHtml(filename)}"]`);
    if (tab) {
        const titleSpan = tab.querySelector('.tab-title');
        if (titleSpan) {
            titleSpan.textContent = modified ? filename + '*' : filename;
        }
    }
    
    // 更新文件信息
    const fileInfo = document.getElementById('file-info');
    if (fileInfo) {
        fileInfo.textContent = modified ? filename + '*' : filename;
    }
}

// 创建带超时的 AbortController（浏览器兼容版本）
function createTimeoutSignal(timeoutMs) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    
    // 返回 signal 和清理函数
    return {
        signal: controller.signal,
        cleanup: () => clearTimeout(timeoutId)
    };
}

// 运行代码
async function runCode() {
    if (HPLIDE.isRunning) return;
    
    const editor = getEditor();
    if (!editor) return;
    
    const code = editor.getValue();
    if (!code.trim()) {
        showOutput('没有可运行的代码', 'error');
        return;
    }
    
    setIsRunning(true);
    const runBtn = document.getElementById('btn-run');
    const statusIndicator = document.getElementById('status-indicator');
    
    if (runBtn) runBtn.disabled = true;
    if (statusIndicator) {
        statusIndicator.textContent = '运行中...';
        statusIndicator.className = 'status-running';
    }
    
    showOutput('正在运行程序...\n', 'info');
    
    let timeoutCleanup = null;
    
    try {
        // 创建 FormData
        const formData = new FormData();
        formData.append('code', code);
        
        // 使用兼容的 timeout 方案
        const timeoutConfig = HPLConfig.getConfig().requestTimeout || CONFIG.DEFAULT_TIMEOUT;
        const { signal, cleanup } = createTimeoutSignal(timeoutConfig);
        timeoutCleanup = cleanup;
        
        // 发送到后端执行
        const apiUrl = HPLConfig.buildApiUrl('/run');
        const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData,
            signal: signal
        });
        
        // 清理超时
        if (timeoutCleanup) {
            timeoutCleanup();
            timeoutCleanup = null;
        }

        const result = await response.json();
        
        if (result.success) {
            showOutput(result.output || '程序执行完成（无输出）', 'success');
        } else {
            showOutput('错误: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            showOutput('⏱️ 请求超时，请检查服务器状态或增加超时时间', 'error');
        } else {
            showOutput('无法连接到 HPL 运行时服务器。\n请确保后端服务器已启动 (python ide/server.py)\n\n错误: ' + error.message, 'error');
        }
    } finally {
        // 确保清理超时
        if (timeoutCleanup) {
            timeoutCleanup();
        }
        
        setIsRunning(false);
        if (runBtn) runBtn.disabled = false;
        if (statusIndicator) {
            statusIndicator.textContent = '就绪';
            statusIndicator.className = 'status-ready';
        }
    }
}

// 显示输出
function showOutput(message, type = 'normal') {
    const outputContent = document.getElementById('output-content');
    if (!outputContent) return;
    
    const line = document.createElement('div');
    line.className = `output-line output-${type}`;
    line.textContent = message; // 使用 textContent 防止 XSS
    outputContent.appendChild(line);
    outputContent.scrollTop = outputContent.scrollHeight;
}

function clearOutput() {
    const outputContent = document.getElementById('output-content');
    if (outputContent) {
        outputContent.innerHTML = '';
    }
}

// 文件树操作
async function refreshFileTree() {
    const fileTree = document.getElementById('file-tree');
    if (!fileTree) return;
    
    // 显示加载状态
    fileTree.innerHTML = '<div class="file-item loading">⏳ 加载中...</div>';
    
    try {
        const apiUrl = HPLConfig.buildApiUrl('/examples');
        const response = await fetch(apiUrl);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.success && result.examples) {
            // 清空现有内容
            fileTree.innerHTML = '';
            
            // 添加文件夹节点
            const folderDiv = document.createElement('div');
            folderDiv.className = 'file-item folder expanded';
            folderDiv.dataset.path = 'examples';
            
            const folderIcon = document.createElement('span');
            folderIcon.className = 'file-icon';
            folderIcon.textContent = '📂';
            
            const folderName = document.createElement('span');
            folderName.className = 'file-name';
            folderName.textContent = 'examples';
            
            folderDiv.appendChild(folderIcon);
            folderDiv.appendChild(folderName);
            fileTree.appendChild(folderDiv);
            
            // 添加所有示例文件
            result.examples.forEach(example => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'file-item file';
                fileDiv.dataset.path = `examples/${example.name}`;
                fileDiv.style.paddingLeft = '20px';
                
                const fileIcon = document.createElement('span');
                fileIcon.className = 'file-icon';
                fileIcon.textContent = '📄';
                
                const fileName = document.createElement('span');
                fileName.className = 'file-name';
                fileName.textContent = example.name; // 使用 textContent 防止 XSS
                
                fileDiv.appendChild(fileIcon);
                fileDiv.appendChild(fileName);
                fileTree.appendChild(fileDiv);
            });
            
            console.log(`文件树已刷新，共 ${result.examples.length} 个文件`);
        } else {
            throw new Error(result.error || '获取文件列表失败');
        }
    } catch (error) {
        console.error('刷新文件树失败:', error);
        fileTree.innerHTML = `<div class="file-item error">❌ 加载失败: ${escapeHtml(error.message)}</div>`;
        showOutput('刷新文件树失败: ' + error.message, 'error');
    }
}

// 统一使用 async/await 风格的 loadExample
async function loadExample(filename) {
    if (!filename) {
        showOutput('错误: 文件名不能为空', 'error');
        return;
    }
    
    // 显示加载状态
    showOutput(`正在加载 ${filename}...`, 'info');
    
    try {
        const apiUrl = HPLConfig.buildApiUrl(`/examples/${encodeURIComponent(filename)}`);
        const response = await fetch(apiUrl);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            openFileInEditor(filename, result.content, false);
            showOutput(`✅ 已加载: ${filename}`, 'success');
        } else {
            throw new Error(result.error || '未知错误');
        }
    } catch (error) {
        showOutput('无法加载示例文件: ' + error.message, 'error');
    }
}

// 面板切换
function switchPanel(panelName) {
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
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化 Monaco Editor
    initMonaco();
    
    // 绑定工具栏按钮
    const btnNew = document.getElementById('btn-new');
    const btnOpen = document.getElementById('btn-open');
    const btnSave = document.getElementById('btn-save');
    const btnRun = document.getElementById('btn-run');
    const btnRefresh = document.getElementById('btn-refresh');
    const btnClearOutput = document.getElementById('btn-clear-output');
    
    if (btnNew) btnNew.addEventListener('click', newFile);
    if (btnOpen) btnOpen.addEventListener('click', openFile);
    if (btnSave) btnSave.addEventListener('click', saveFile);
    if (btnRun) btnRun.addEventListener('click', runCode);
    if (btnRefresh) btnRefresh.addEventListener('click', refreshFileTree);
    if (btnClearOutput) btnClearOutput.addEventListener('click', clearOutput);
    
    // 文件输入
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.addEventListener('change', handleFileOpen);
    
    // 保存对话框
    const btnSaveConfirm = document.getElementById('btn-save-confirm');
    const btnSaveCancel = document.getElementById('btn-save-cancel');
    const btnSaveClose = document.getElementById('btn-save-close');
    
    if (btnSaveConfirm) btnSaveConfirm.addEventListener('click', confirmSave);
    if (btnSaveCancel) btnSaveCancel.addEventListener('click', hideSaveDialog);
    if (btnSaveClose) btnSaveClose.addEventListener('click', hideSaveDialog);
    
    // 配置对话框
    const btnConfig = document.getElementById('btn-config');
    const btnConfigCancel = document.getElementById('btn-config-cancel');
    const btnConfigClose = document.getElementById('btn-config-close');
    const btnConfigSave = document.getElementById('btn-config-save');
    const btnConfigReset = document.getElementById('btn-config-reset');
    const btnTestConnection = document.getElementById('btn-test-connection');
    
    if (btnConfig) btnConfig.addEventListener('click', showConfigDialog);
    if (btnConfigCancel) btnConfigCancel.addEventListener('click', hideConfigDialog);
    if (btnConfigClose) btnConfigClose.addEventListener('click', hideConfigDialog);
    if (btnConfigSave) btnConfigSave.addEventListener('click', saveConfig);
    if (btnConfigReset) btnConfigReset.addEventListener('click', resetConfig);
    if (btnTestConnection) btnTestConnection.addEventListener('click', testServerConnection);
    
    // 面板切换
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.addEventListener('click', () => switchPanel(tab.dataset.panel));
    });
    
    // 欢迎页面按钮
    const actionNew = document.getElementById('action-new');
    const actionOpen = document.getElementById('action-open');
    const actionExample = document.getElementById('action-example');
    
    if (actionNew) actionNew.addEventListener('click', newFile);
    if (actionOpen) actionOpen.addEventListener('click', openFile);
    if (actionExample) actionExample.addEventListener('click', () => {
        loadExample('example.hpl');
    });
    
    // 文件树点击（使用事件委托，支持动态添加的元素）
    const fileTree = document.getElementById('file-tree');
    if (fileTree) {
        fileTree.addEventListener('click', (e) => {
            const item = e.target.closest('.file-item');
            if (!item) return;
            
            const path = item.dataset.path;
            if (path && !item.classList.contains('folder')) {
                // 从路径提取文件名
                const filename = path.split('/').pop();
                loadExample(filename);
            }
        });
    }
    
    // 页面加载时自动刷新文件树
    refreshFileTree();

    
    // 键盘快捷键
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'n':
                    e.preventDefault();
                    newFile();
                    break;
                case 'o':
                    e.preventDefault();
                    openFile();
                    break;
                case 's':
                    e.preventDefault();
                    saveFile();
                    break;
                case ',':
                    if (!e.shiftKey) {
                        e.preventDefault();
                        showConfigDialog();
                    }
                    break;
            }
        } else if (e.key === 'F5') {
            e.preventDefault();
            runCode();
        } else if (e.key === 'Escape') {
            // ESC关闭打开的对话框
            hideSaveDialog();
            hideConfigDialog();
        }
    });

    
    console.log('HPL IDE 初始化完成');
});
