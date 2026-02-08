/**
 * HPL IDE - 编辑器模块
 * 管理 Monaco Editor 的初始化、配置和功能
 */

const HPLEditor = {
    // 编辑器实例
    instance: null,
    
    // 错误装饰器集合
    errorDecorations: [],
    
    // 配置常量
    CONFIG: {
        MONACO_VERSION: '0.44.0',
        DEFAULT_FONT_SIZE: 14
    },

    /**
     * HPL 自动补全提供程序
     */
    completionProvider: {
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
    },

    /**
     * 初始化 Monaco Editor
     */
    init() {
        return new Promise((resolve, reject) => {
            try {
                require.config({ 
                    paths: { 
                        'vs': `https://cdn.jsdelivr.net/npm/monaco-editor@${this.CONFIG.MONACO_VERSION}/min/vs` 
                    }
                });

                require(['vs/editor/editor.main'], () => {
                    try {
                        this._registerLanguage();
                        this._createEditor();
                        this._setupEventListeners();
                        console.log('Monaco Editor 初始化完成');
                        resolve(this.instance);
                    } catch (error) {
                        console.error('Monaco Editor 初始化失败:', error);
                        reject(error);
                    }
                }, (error) => {
                    console.error('加载 Monaco Editor 失败:', error);
                    reject(error);
                });
            } catch (error) {
                console.error('初始化 Monaco Editor 时发生错误:', error);
                reject(error);
            }
        });
    },

    /**
     * 注册 HPL 语言
     */
    _registerLanguage() {
        // 注册语言
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
        monaco.languages.registerCompletionItemProvider('hpl', this.completionProvider);
    },

    /**
     * 创建编辑器实例
     */
    _createEditor() {
        const config = HPLConfig.getConfig();
        
        this.instance = monaco.editor.create(document.getElementById('editor'), {
            value: '',
            language: 'hpl',
            theme: config.editorTheme || 'vs-dark',
            automaticLayout: true,
            minimap: { enabled: config.minimap !== false },
            fontSize: config.fontSize || this.CONFIG.DEFAULT_FONT_SIZE,
            fontFamily: 'Consolas, "Courier New", monospace',
            lineNumbers: 'on',
            roundedSelection: false,
            scrollBeyondLastLine: false,
            readOnly: false,
            wordWrap: config.wordWrap || 'on',
            folding: true,
            renderWhitespace: 'selection',
            matchBrackets: 'always',
            autoIndent: 'full',
            formatOnPaste: true,
            formatOnType: true,
            tabSize: 2,
            insertSpaces: true,
        });
    },

    /**
     * 设置事件监听
     */
    _setupEventListeners() {
        // 监听光标位置变化
        this.instance.onDidChangeCursorPosition((e) => {
            HPLUI.updateCursorInfo(e.position.lineNumber, e.position.column);
        });

        // 监听内容变化
        this.instance.onDidChangeModelContent(() => {
            // 清除错误高亮
            this.clearErrorHighlights();
            
            // 通知文件管理器内容已变更
            if (typeof HPLFileManager !== 'undefined') {
                HPLFileManager.markCurrentFileAsModified();
            }
        });
    },

    /**
     * 获取编辑器值
     */
    getValue() {
        return this.instance ? this.instance.getValue() : '';
    },

    /**
     * 设置编辑器值
     */
    setValue(value) {
        if (this.instance) {
            this.instance.setValue(value);
        }
    },

    /**
     * 设置编辑器选项
     */
    updateOptions(options) {
        if (this.instance) {
            this.instance.updateOptions(options);
        }
    },

    /**
     * 设置编辑器主题
     */
    setTheme(theme) {
        if (monaco && monaco.editor) {
            monaco.editor.setTheme(theme);
        }
    },

    /**
     * 聚焦编辑器
     */
    focus() {
        if (this.instance) {
            this.instance.focus();
        }
    },

    /**
     * 高亮错误行
     */
    highlightErrorLine(lineNumber, column = 1) {
        if (!this.instance || !lineNumber) return;
        
        // 清除之前的错误高亮
        this.clearErrorHighlights();
        
        // 添加新的错误高亮
        const decoration = {
            range: new monaco.Range(lineNumber, 1, lineNumber, 1),
            options: {
                isWholeLine: true,
                className: 'error-line-highlight',
                glyphMarginClassName: 'error-glyph-margin',
                overviewRuler: {
                    color: 'rgba(255, 0, 0, 0.8)',
                    position: monaco.editor.OverviewRulerLane.Full
                }
            }
        };
        
        this.errorDecorations = this.instance.deltaDecorations([], [decoration]);
        
        // 滚动到错误行
        this.instance.revealLineInCenter(lineNumber);
        
        // 设置光标位置
        this.instance.setPosition({ lineNumber: lineNumber, column: column });
    },

    /**
     * 清除错误高亮
     */
    clearErrorHighlights() {
        if (!this.instance || this.errorDecorations.length === 0) return;
        
        this.instance.deltaDecorations(this.errorDecorations, []);
        this.errorDecorations = [];
    },

    /**
     * 获取当前光标位置
     */
    getPosition() {
        return this.instance ? this.instance.getPosition() : { lineNumber: 1, column: 1 };
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLEditor;
}
