/**
 * HPL IDE - 主应用程序
 * 集成 Monaco Editor，提供 HPL 语言支持
 */

// 全局变量
let editor = null;
let currentFile = null;
let openFiles = new Map();
let isRunning = false;

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

// 初始化 Monaco Editor
function initMonaco() {
    require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs' }});

    require(['vs/editor/editor.main'], function() {
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
        editor = monaco.editor.create(document.getElementById('editor'), {
            value: '',
            language: 'hpl',
            theme: 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: true },
            fontSize: 14,
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
        editor.onDidChangeCursorPosition((e) => {
            document.getElementById('cursor-info').textContent = 
                `行 ${e.position.lineNumber}, 列 ${e.position.column}`;
        });

        // 监听内容变化
        editor.onDidChangeModelContent(() => {
            if (currentFile) {
                markFileAsModified(currentFile, true);
            }
        });

        // 隐藏欢迎页面
        document.getElementById('welcome-page').style.display = 'none';
        
        console.log('Monaco Editor 初始化完成');
    });
}

// 文件操作
function newFile() {
    const filename = 'untitled.hpl';
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
    document.getElementById('file-input').click();
}

function handleFileOpen(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        openFileInEditor(file.name, e.target.result, false);
    };
    reader.readAsText(file);
    
    // 重置 input
    event.target.value = '';
}

function saveFile() {
    if (!currentFile) {
        showSaveDialog();
        return;
    }

    const content = editor.getValue();
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = currentFile.replace('*', '');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    markFileAsModified(currentFile, false);
    showOutput('文件已保存: ' + currentFile.replace('*', ''), 'success');
}

function showSaveDialog() {
    document.getElementById('save-dialog').classList.remove('hidden');
    document.getElementById('save-filename').value = 'untitled.hpl';
    document.getElementById('save-filename').focus();
}

function hideSaveDialog() {
    document.getElementById('save-dialog').classList.add('hidden');
}

// 配置对话框
function showConfigDialog() {
    const config = HPLConfig.getConfig();
    document.getElementById('config-api-url').value = config.apiBaseUrl;
    document.getElementById('config-timeout').value = config.requestTimeout;
    document.getElementById('config-font-size').value = config.fontSize;
    document.getElementById('config-theme').value = config.editorTheme;
    document.getElementById('config-dialog').classList.remove('hidden');
}

function hideConfigDialog() {
    document.getElementById('config-dialog').classList.add('hidden');
}

async function testServerConnection() {
    const btn = document.getElementById('btn-test-connection');
    const originalText = btn.textContent;
    btn.textContent = '⏳ 测试中...';
    btn.disabled = true;
    
    const result = await HPLConfig.testConnection();
    
    btn.textContent = originalText;
    btn.disabled = false;
    
    if (result.success) {
        showOutput('✅ 连接成功！服务器运行正常', 'success');
    } else {
        showOutput('❌ 连接失败: ' + result.error, 'error');
    }
}

function saveConfig() {
    const apiUrl = document.getElementById('config-api-url').value.trim();
    const timeout = parseInt(document.getElementById('config-timeout').value) || 30000;
    const fontSize = parseInt(document.getElementById('config-font-size').value) || 14;
    const theme = document.getElementById('config-theme').value;
    
    if (!apiUrl) {
        showOutput('错误: API 地址不能为空', 'error');
        return;
    }
    
    HPLConfig.saveConfig({
        apiBaseUrl: apiUrl,
        requestTimeout: timeout,
        fontSize: fontSize,
        editorTheme: theme
    });
    
    // 应用字体大小
    if (editor) {
        editor.updateOptions({ fontSize: fontSize });
    }
    
    hideConfigDialog();
    showOutput('配置已保存', 'success');
}

function resetConfig() {
    HPLConfig.resetConfig();
    const config = HPLConfig.getConfig();
    document.getElementById('config-api-url').value = config.apiBaseUrl;
    document.getElementById('config-timeout').value = config.requestTimeout;
    document.getElementById('config-font-size').value = config.fontSize;
    document.getElementById('config-theme').value = config.editorTheme;
    showOutput('配置已重置为默认值', 'info');
}

function confirmSave() {

    const filename = document.getElementById('save-filename').value;
    if (!filename) return;
    
    openFileInEditor(filename, editor.getValue(), true);
    hideSaveDialog();
    saveFile();
}

// 在编辑器中打开文件
function openFileInEditor(filename, content, isNew = false) {
    // 检查是否已打开
    if (openFiles.has(filename)) {
        switchToFile(filename);
        return;
    }

    const displayName = isNew ? filename + '*' : filename;
    openFiles.set(filename, {
        content: content,
        isModified: isNew,
        isNew: isNew
    });

    // 创建标签页
    createTab(filename, displayName);
    
    // 切换到新文件
    switchToFile(filename);
    
    // 更新文件信息
    document.getElementById('file-info').textContent = filename;
}

function createTab(filename, displayName) {
    const tabsContainer = document.getElementById('tabs-container');
    
    const tab = document.createElement('div');
    tab.className = 'tab';
    tab.dataset.file = filename;
    tab.innerHTML = `
        <span class="tab-icon">📄</span>
        <span class="tab-title">${displayName}</span>
        <span class="tab-close">×</span>
    `;
    
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
    
    // 保存当前文件内容
    if (currentFile && editor) {
        const fileData = openFiles.get(currentFile);
        if (fileData) {
            fileData.content = editor.getValue();
        }
    }
    
    // 切换文件
    currentFile = filename;
    const fileData = openFiles.get(filename);
    
    if (editor && fileData) {
        editor.setValue(fileData.content);
        editor.focus();
    }
    
    // 更新文件信息
    document.getElementById('file-info').textContent = 
        fileData?.isModified ? filename + '*' : filename;
    
    // 隐藏欢迎页面
    document.getElementById('welcome-page').style.display = 'none';
}

function closeFile(filename) {
    const fileData = openFiles.get(filename);
    
    // 如果有修改，提示保存
    if (fileData?.isModified) {
        if (!confirm(`文件 ${filename} 有未保存的更改，确定要关闭吗？`)) {
            return;
        }
    }
    
    openFiles.delete(filename);
    
    // 移除标签页
    const tab = document.querySelector(`.tab[data-file="${filename}"]`);
    if (tab) {
        tab.remove();
    }
    
    // 如果关闭的是当前文件，切换到其他文件
    if (currentFile === filename) {
        const remainingFiles = Array.from(openFiles.keys());
        if (remainingFiles.length > 0) {
            switchToFile(remainingFiles[0]);
        } else {
            currentFile = null;
            editor.setValue('');
            document.getElementById('welcome-page').style.display = 'flex';
            document.getElementById('file-info').textContent = '未选择文件';
        }
    }
}

function markFileAsModified(filename, modified) {
    const fileData = openFiles.get(filename);
    if (!fileData) return;
    
    fileData.isModified = modified;
    
    // 更新标签页标题
    const tab = document.querySelector(`.tab[data-file="${filename}"]`);
    if (tab) {
        const titleSpan = tab.querySelector('.tab-title');
        titleSpan.textContent = modified ? filename + '*' : filename;
    }
    
    // 更新文件信息
    document.getElementById('file-info').textContent = 
        modified ? filename + '*' : filename;
}

// 运行代码
async function runCode() {
    if (isRunning) return;
    
    const code = editor.getValue();
    if (!code.trim()) {
        showOutput('没有可运行的代码', 'error');
        return;
    }
    
    isRunning = true;
    document.getElementById('btn-run').disabled = true;
    document.getElementById('status-indicator').textContent = '运行中...';
    document.getElementById('status-indicator').className = 'status-running';
    
    showOutput('正在运行程序...\n', 'info');
    
    try {
        // 创建 FormData
        const formData = new FormData();
        formData.append('code', code);
        
        // 发送到后端执行
        const apiUrl = HPLConfig.buildApiUrl('/run');
        const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData,
            signal: AbortSignal.timeout(HPLConfig.getConfig().requestTimeout)
        });

        
        const result = await response.json();
        
        if (result.success) {
            showOutput(result.output || '程序执行完成（无输出）', 'success');
        } else {
            showOutput('错误: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        showOutput('无法连接到 HPL 运行时服务器。\n请确保后端服务器已启动 (python ide/server.py)\n\n错误: ' + error.message, 'error');
    } finally {
        isRunning = false;
        document.getElementById('btn-run').disabled = false;
        document.getElementById('status-indicator').textContent = '就绪';
        document.getElementById('status-indicator').className = 'status-ready';
    }
}

// 显示输出
function showOutput(message, type = 'normal') {
    const outputContent = document.getElementById('output-content');
    const line = document.createElement('div');
    line.className = `output-line output-${type}`;
    line.textContent = message;
    outputContent.appendChild(line);
    outputContent.scrollTop = outputContent.scrollHeight;
}

function clearOutput() {
    document.getElementById('output-content').innerHTML = '';
}

// 文件树操作
function refreshFileTree() {
    // 这里可以实现从服务器获取文件列表
    console.log('刷新文件树');
}

function loadExample(filename) {
    // 从后端 API 加载示例文件
    const apiUrl = HPLConfig.buildApiUrl(`/examples/${filename}`);
    fetch(apiUrl)

        .then(response => response.json())
        .then(result => {
            if (result.success) {
                openFileInEditor(filename, result.content, false);
            } else {
                showOutput('无法加载示例文件: ' + (result.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            showOutput('无法加载示例文件: ' + error.message, 'error');
        });
}


// 面板切换
function switchPanel(panelName) {
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.panel === panelName);
    });
    
    document.getElementById('output-panel').classList.toggle('hidden', panelName !== 'output');
    document.getElementById('problems-panel').classList.toggle('hidden', panelName !== 'problems');
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化 Monaco Editor
    initMonaco();
    
    // 绑定工具栏按钮
    document.getElementById('btn-new').addEventListener('click', newFile);
    document.getElementById('btn-open').addEventListener('click', openFile);
    document.getElementById('btn-save').addEventListener('click', saveFile);
    document.getElementById('btn-run').addEventListener('click', runCode);
    document.getElementById('btn-refresh').addEventListener('click', refreshFileTree);
    document.getElementById('btn-clear-output').addEventListener('click', clearOutput);
    
    // 文件输入
    document.getElementById('file-input').addEventListener('change', handleFileOpen);
    
    // 保存对话框
    document.getElementById('btn-save-confirm').addEventListener('click', confirmSave);
    document.getElementById('btn-save-cancel').addEventListener('click', hideSaveDialog);
    
    // 配置对话框
    document.getElementById('btn-config').addEventListener('click', showConfigDialog);
    document.getElementById('btn-config-cancel').addEventListener('click', hideConfigDialog);
    document.getElementById('btn-config-save').addEventListener('click', saveConfig);
    document.getElementById('btn-config-reset').addEventListener('click', resetConfig);
    document.getElementById('btn-test-connection').addEventListener('click', testServerConnection);

    
    // 面板切换
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.addEventListener('click', () => switchPanel(tab.dataset.panel));
    });
    
    // 欢迎页面按钮
    document.getElementById('action-new').addEventListener('click', newFile);
    document.getElementById('action-open').addEventListener('click', openFile);
    document.getElementById('action-example').addEventListener('click', () => {
        loadExample('example.hpl');
    });
    
    // 文件树点击
    document.querySelectorAll('.file-item').forEach(item => {
        item.addEventListener('click', () => {
            const path = item.dataset.path;
            if (path && !item.classList.contains('folder')) {
                // 从路径提取文件名
                const filename = path.split('/').pop();
                loadExample(filename);
            }
        });
    });
    
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
            }
        } else if (e.key === 'F5') {
            e.preventDefault();
            runCode();
        }
    });
    
    console.log('HPL IDE 初始化完成');
});
