/**
 * HPL IDE - 编辑器模块
 * 管理 Monaco Editor 的初始化、配置和功能
 */

const HPLEditor = {
    // 编辑器实例
    instance: null,
    
    // 错误装饰器集合
    errorDecorations: [],
    
    // 错误列表（支持多错误导航）
    errorList: [],
    currentErrorIndex: -1,
    
    // 配置常量
    CONFIG: {
        MONACO_VERSION: '0.44.0',
        DEFAULT_FONT_SIZE: 14
    },


    /**
     * 代码片段定义
     */
    snippets: [
        {
            label: 'hpl-template',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
                'includes:',
                '  - ${1:file.hpl}',
                '',
                'imports:',
                '  - ${2:math}',
                '',
                'classes:',
                '  ${3:MyClass}:',
                '    ${4:method}: () => {',
                '      ${5:// code}',
                '    }',
                '',
                'objects:',
                '  ${6:myObject}: ${3:MyClass}()',
                '',
                'main: () => {',
                '  ${7:// main code}',
                '}',
                '',
                'call: main()'
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: '完整的HPL文件模板'
        },
        {
            label: 'class-template',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
                '${1:ClassName}:',
                '  ${2:parent}: ${3:BaseClass}',
                '  ${4:method}: () => {',
                '    ${5:// method code}',
                '  }'
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: '类定义模板'
        },
        {
            label: 'for-loop',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: 'for (${1:i} = ${2:0}; ${1:i} < ${3:count}; ${1:i}++) :\n    ${4:// loop body}',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: 'for循环模板'
        },
        {
            label: 'if-else',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
                'if (${1:condition}) :',
                '    ${2:// if body}',
                'else :',
                '    ${3:// else body}'
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: 'if-else条件语句模板'
        },
        {
            label: 'try-catch',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: [
                'try :',
                '    ${1:// try block}',
                'catch (${2:error}) :',
                '    ${3:// catch block}'
            ].join('\n'),
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: 'try-catch异常处理模板'
        },
        {
            label: 'method',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: '${1:methodName}: (${2:params}) => {\n    ${3:// method body}\n  }',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: '方法定义模板'
        }
    ],

    /**
     * 获取当前代码上下文
     */
    getContext(model, position) {
        const textUntilPosition = model.getValueInRange({
            startLineNumber: 1,
            startColumn: 1,
            endLineNumber: position.lineNumber,
            endColumn: position.column
        });
        
        const lines = textUntilPosition.split('\n');
        const currentLine = lines[lines.length - 1];
        const currentIndent = currentLine.match(/^(\s*)/)[1].length;
        
        // 检测当前所在的节
        let currentSection = null;
        let currentClass = null;
        let inMethod = false;
        
        for (let i = lines.length - 1; i >= 0; i--) {
            const line = lines[i];
            const indent = line.match(/^(\s*)/)[1].length;
            const trimmed = line.trim();
            
            // 检测节标题
            if (trimmed === 'classes:' || trimmed === 'objects:' || 
                trimmed === 'includes:' || trimmed === 'imports:' ||
                trimmed === 'main:' || trimmed.startsWith('call:')) {
                if (indent === 0) {
                    currentSection = trimmed.replace(':', '');
                    break;
                }
            }
            
            // 检测类定义
            if (indent === 2 && trimmed.endsWith(':') && !trimmed.includes(' ')) {
                currentClass = trimmed.replace(':', '');
            }
            
            // 检测是否在方法内
            if (trimmed.includes('=>') && indent >= 4) {
                inMethod = true;
            }
        }
        
        return {
            section: currentSection,
            className: currentClass,
            inMethod: inMethod,
            indent: currentIndent,
            currentLine: currentLine.trim()
        };
    },

    /**
     * 解析已定义的类名
     */
    getDefinedClasses(model) {
        const content = model.getValue();
        const classRegex = /^  (\w+):/gm;
        const classes = [];
        let match;
        while ((match = classRegex.exec(content)) !== null) {
            classes.push(match[1]);
        }
        return [...new Set(classes)]; // 去重
    },

    /**
     * 解析已导入的模块
     */
    getImportedModules(model) {
        const content = model.getValue();
        const importRegex = /^  - (\w+)$/gm;
        const modules = [];
        let match;
        while ((match = importRegex.exec(content)) !== null) {
            modules.push(match[1]);
        }
        return modules;
    },

    /**
     * HPL 增强自动补全提供程序（支持上下文感知）
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

            const context = HPLEditor.getContext(model, position);
            const suggestions = [];

            // 根据上下文提供不同的补全建议
            if (context.section === 'imports') {
                // 在imports节，建议标准库模块
                const stdModules = ['math', 'io', 'json', 'os', 'time', 'sys', 're', 'random'];
                const importedModules = HPLEditor.getImportedModules(model);
                
                stdModules.forEach(mod => {
                    if (!importedModules.includes(mod)) {
                        suggestions.push({
                            label: mod,
                            kind: monaco.languages.CompletionItemKind.Module,
                            insertText: mod,
                            documentation: `标准库模块: ${mod}`,
                            range
                        });
                    }
                });
            } else if (context.section === 'classes') {
                if (context.indent === 4 && context.inMethod) {
                    // 在方法内部，建议控制流和关键字
                    suggestions.push(
                        { label: 'if', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'if (${1:condition}) :\n    ${2:// code}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '条件语句', range },
                        { label: 'for', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'for (${1:i} = ${2:0}; ${1:i} < ${3:count}; ${1:i}++) :\n    ${4:// code}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: 'for循环', range },
                        { label: 'while', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'while (${1:condition}) :\n    ${2:// code}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: 'while循环', range },
                        { label: 'return', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'return ${1:value}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '返回值', range },
                        { label: 'this', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'this', documentation: '当前对象引用', range }
                    );
                } else if (context.indent === 2) {
                    // 在类定义级别，建议parent和方法模板
                    suggestions.push(
                        { label: 'parent', kind: monaco.languages.CompletionItemKind.Property, insertText: 'parent: ${1:BaseClass}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '指定父类', range },
                        { label: 'method', kind: monaco.languages.CompletionItemKind.Snippet, insertText: '${1:methodName}: (${2:params}) => {\n    ${3:// code}\n  }', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '方法定义', range }
                    );
                }
            } else if (context.section === 'objects') {
                // 在objects节，建议已定义的类名
                const definedClasses = HPLEditor.getDefinedClasses(model);
                definedClasses.forEach(className => {
                    suggestions.push({
                        label: className,
                        kind: monaco.languages.CompletionItemKind.Class,
                        insertText: `${className}()`,
                        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
                        documentation: `实例化 ${className} 类`,
                        range
                    });
                });
            } else if (context.section === 'main') {
                // 在main函数中，建议控制流和内置函数
                suggestions.push(
                    { label: 'if', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'if (${1:condition}) :\n    ${2:// code}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '条件语句', range },
                    { label: 'for', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'for (${1:i} = ${2:0}; ${1:i} < ${3:count}; ${1:i}++) :\n    ${4:// code}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: 'for循环', range },
                    { label: 'while', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'while (${1:condition}) :\n    ${2:// code}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: 'while循环', range },
                    { label: 'try', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'try :\n    ${1:// code}\ncatch (${2:error}) :\n    ${3:// handle}', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: 'try-catch', range }
                );
                
                // 添加对象调用建议
                const definedClasses = HPLEditor.getDefinedClasses(model);
                definedClasses.forEach(className => {
                    suggestions.push({
                        label: `${className.toLowerCase()}.`,
                        kind: monaco.languages.CompletionItemKind.Variable,
                        insertText: `${className.toLowerCase()}.`,
                        documentation: `访问 ${className} 对象`,
                        range
                    });
                });
            }

            // 始终添加代码片段
            HPLEditor.snippets.forEach(snippet => {
                suggestions.push({
                    ...snippet,
                    range
                });
            });

            // 添加通用关键字（如果不在特定上下文中或作为补充）
            const commonKeywords = [
                { label: 'includes', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'includes:\n  - ', documentation: '包含其他 HPL 文件', range },
                { label: 'classes', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'classes:\n  ', documentation: '定义类', range },
                { label: 'objects', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'objects:\n  ', documentation: '实例化对象', range },
                { label: 'main', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'main: () => {\n    \n  }', documentation: '主函数', range },
                { label: 'call', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'call: main()', documentation: '调用主函数', range },
                { label: 'imports', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'imports:\n  - ', documentation: '导入标准库模块', range }
            ];
            
            // 只在顶层或不确定上下文时添加通用关键字
            if (!context.section || context.indent === 0) {
                suggestions.push(...commonKeywords);
            }

            // 始终添加内置函数
            const builtinFunctions = [
                { label: 'echo', kind: monaco.languages.CompletionItemKind.Function, insertText: 'echo(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '输出值到控制台', range },
                { label: 'len', kind: monaco.languages.CompletionItemKind.Function, insertText: 'len(${1:array_or_string})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取数组或字符串长度', range },
                { label: 'int', kind: monaco.languages.CompletionItemKind.Function, insertText: 'int(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '转换为整数', range },
                { label: 'str', kind: monaco.languages.CompletionItemKind.Function, insertText: 'str(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '转换为字符串', range },
                { label: 'type', kind: monaco.languages.CompletionItemKind.Function, insertText: 'type(${1:value})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取值类型', range },
                { label: 'abs', kind: monaco.languages.CompletionItemKind.Function, insertText: 'abs(${1:number})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取绝对值', range },
                { label: 'max', kind: monaco.languages.CompletionItemKind.Function, insertText: 'max(${1:a}, ${2:b})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取最大值', range },
                { label: 'min', kind: monaco.languages.CompletionItemKind.Function, insertText: 'min(${1:a}, ${2:b})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '获取最小值', range },
                { label: 'range', kind: monaco.languages.CompletionItemKind.Function, insertText: 'range(${1:start}, ${2:end})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '生成数字范围', range },
                { label: 'sum', kind: monaco.languages.CompletionItemKind.Function, insertText: 'sum(${1:array})', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, documentation: '求和数组元素', range }
            ];
            suggestions.push(...builtinFunctions);

            // 添加布尔值常量
            suggestions.push(
                { label: 'true', kind: monaco.languages.CompletionItemKind.Constant, insertText: 'true', documentation: '真', range },
                { label: 'false', kind: monaco.languages.CompletionItemKind.Constant, insertText: 'false', documentation: '假', range },
                { label: 'null', kind: monaco.languages.CompletionItemKind.Constant, insertText: 'null', documentation: '空值', range }
            );

            return { suggestions };
        }
    },


    /**
     * 初始化 Monaco Editor（带重试机制）
     */
    init(retryCount = 0) {
        const maxRetries = 3;
        const baseDelay = 1000; // 1秒基础延迟
        
        return new Promise((resolve, reject) => {
            const attemptLoad = () => {
                console.log(`尝试加载 Monaco Editor (尝试 ${retryCount + 1}/${maxRetries + 1})...`);
                
                try {
                    require.config({ 
                        paths: { 
                            'vs': `https://cdn.jsdelivr.net/npm/monaco-editor@${this.CONFIG.MONACO_VERSION}/min/vs` 
                        },
                        // 添加错误回调配置
                        onError: (err) => {
                            console.warn('RequireJS 错误:', err);
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
                            // 尝试降级方案
                            this._initFallback(retryCount, maxRetries, baseDelay, resolve, reject, error);
                        }
                    }, (error) => {
                        // AMD 加载失败的回调
                        console.error('加载 Monaco Editor 失败:', error);
                        this._initFallback(retryCount, maxRetries, baseDelay, resolve, reject, error);
                    });
                } catch (error) {
                    console.error('初始化 Monaco Editor 时发生错误:', error);
                    this._initFallback(retryCount, maxRetries, baseDelay, resolve, reject, error);
                }
            };
            
            attemptLoad();
        });
    },

    /**
     * 初始化失败后的降级处理
     */
    _initFallback(retryCount, maxRetries, baseDelay, resolve, reject, error) {
        if (retryCount < maxRetries) {
            const delay = baseDelay * Math.pow(2, retryCount); // 指数退避
            console.log(`${delay}ms 后重试...`);
            
            setTimeout(() => {
                this.init(retryCount + 1).then(resolve).catch(reject);
            }, delay);
        } else {
            // 所有重试失败，显示降级界面
            console.error('Monaco Editor 加载失败，启用降级模式');
            this._showFallbackEditor();
            reject(error);
        }
    },

    /**
     * 显示降级编辑器（简单的 textarea）
     */
    _showFallbackEditor() {
        const editorContainer = document.getElementById('editor');
        if (!editorContainer) return;
        
        // 创建降级编辑器
        const fallbackDiv = document.createElement('div');
        fallbackDiv.style.cssText = 'width:100%;height:100%;background:#1e1e1e;color:#ccc;padding:10px;';
        
        const textarea = document.createElement('textarea');
        textarea.id = 'fallback-editor';
        textarea.style.cssText = 'width:100%;height:100%;background:#1e1e1e;color:#ccc;border:none;resize:none;font-family:Consolas,monospace;font-size:14px;outline:none;';
        textarea.placeholder = '-- Monaco Editor 加载失败，使用降级编辑器 --\n\n请检查网络连接或刷新页面重试。\n\n支持的基本编辑功能：\n- 输入和编辑代码\n- Ctrl+S 保存\n- 代码将被发送到后端执行';
        
        fallbackDiv.appendChild(textarea);
        editorContainer.appendChild(fallbackDiv);
        
        // 添加获取/设置值的方法兼容
        this.instance = {
            getValue: () => textarea.value,
            setValue: (v) => { textarea.value = v; },
            focus: () => textarea.focus(),
            updateOptions: () => {},
            revealLineInCenter: () => {},
            setPosition: () => {},
            onDidChangeCursorPosition: () => ({ dispose: () => {} }),
            onDidChangeModelContent: (cb) => {
                textarea.addEventListener('input', cb);
                return { dispose: () => {} };
            },
            deltaDecorations: () => []
        };
        
        // 显示警告
        if (typeof HPLUI !== 'undefined') {
            HPLUI.showOutput('⚠️ Monaco Editor 加载失败，已启用降级编辑器', 'warning');
        }
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
     * 高亮错误行（支持多错误）
     */
    highlightErrorLine(lineNumber, column = 1, errorMessage = '') {
        if (!this.instance || !lineNumber) return;
        
        // 添加错误到列表
        const errorInfo = {
            lineNumber: parseInt(lineNumber),
            column: parseInt(column) || 1,
            message: errorMessage || `错误 at line ${lineNumber}`
        };
        
        // 避免重复添加相同位置的错误
        const exists = this.errorList.some(e => e.lineNumber === errorInfo.lineNumber && e.column === errorInfo.column);
        if (!exists) {
            this.errorList.push(errorInfo);
        }
        
        // 添加错误高亮装饰
        const decoration = {
            range: new monaco.Range(lineNumber, 1, lineNumber, 1),
            options: {
                isWholeLine: true,
                className: 'error-line-highlight',
                glyphMarginClassName: 'error-glyph-margin',
                overviewRuler: {
                    color: 'rgba(255, 0, 0, 0.8)',
                    position: monaco.editor.OverviewRulerLane.Full
                },
                hoverMessage: { value: errorMessage || 'Error' }
            }
        };
        
        this.errorDecorations = this.instance.deltaDecorations(this.errorDecorations, [...this.errorDecorations, decoration]);
        
        // 滚动到错误行
        this.instance.revealLineInCenter(lineNumber);
        
        // 设置光标位置
        this.instance.setPosition({ lineNumber: lineNumber, column: column });
        
        // 更新状态栏错误计数
        this._updateErrorCount();
    },

    /**
     * 设置多个错误（用于批量错误显示）
     */
    setErrors(errors) {
        if (!this.instance) return;
        
        // 清除现有错误
        this.clearAllErrors();
        
        // 添加所有错误
        errors.forEach(error => {
            if (error.line) {
                this.errorList.push({
                    lineNumber: parseInt(error.line),
                    column: parseInt(error.column) || 1,
                    message: error.message || error.error || 'Error',
                    type: error.type || 'error'
                });
            }
        });
        
        // 创建所有错误装饰
        const decorations = this.errorList.map(error => ({
            range: new monaco.Range(error.lineNumber, 1, error.lineNumber, 1),
            options: {
                isWholeLine: true,
                className: error.type === 'warning' ? 'warning-line-highlight' : 'error-line-highlight',
                glyphMarginClassName: error.type === 'warning' ? 'warning-glyph-margin' : 'error-glyph-margin',
                overviewRuler: {
                    color: error.type === 'warning' ? 'rgba(204, 167, 0, 0.8)' : 'rgba(255, 0, 0, 0.8)',
                    position: monaco.editor.OverviewRulerLane.Full
                },
                hoverMessage: { value: error.message }
            }
        }));
        
        this.errorDecorations = this.instance.deltaDecorations([], decorations);
        
        // 更新状态栏
        this._updateErrorCount();
        
        // 导航到第一个错误
        if (this.errorList.length > 0) {
            this.currentErrorIndex = 0;
            this._navigateToError(0);
        }
    },

    /**
     * 导航到下一个错误 (F8)
     */
    goToNextError() {
        if (this.errorList.length === 0) {
            if (typeof HPLUI !== 'undefined') {
                HPLUI.showOutput('没有错误需要导航', 'info');
            }
            return;
        }
        
        this.currentErrorIndex = (this.currentErrorIndex + 1) % this.errorList.length;
        this._navigateToError(this.currentErrorIndex);
    },

    /**
     * 导航到上一个错误 (Shift+F8)
     */
    goToPreviousError() {
        if (this.errorList.length === 0) {
            if (typeof HPLUI !== 'undefined') {
                HPLUI.showOutput('没有错误需要导航', 'info');
            }
            return;
        }
        
        this.currentErrorIndex = (this.currentErrorIndex - 1 + this.errorList.length) % this.errorList.length;
        this._navigateToError(this.currentErrorIndex);
    },

    /**
     * 内部方法：导航到指定错误索引
     */
    _navigateToError(index) {
        const error = this.errorList[index];
        if (!error || !this.instance) return;
        
        // 滚动到错误行
        this.instance.revealLineInCenter(error.lineNumber);
        
        // 设置光标位置
        this.instance.setPosition({ 
            lineNumber: error.lineNumber, 
            column: error.column 
        });
        
        // 聚焦编辑器
        this.instance.focus();
        
        // 显示导航信息
        if (typeof HPLUI !== 'undefined') {
            HPLUI.showOutput(`错误 ${index + 1}/${this.errorList.length}: 第 ${error.lineNumber} 行 - ${error.message}`, 'info');
        }
    },

    /**
     * 获取错误统计信息
     */
    getErrorStats() {
        const errors = this.errorList.filter(e => e.type !== 'warning');
        const warnings = this.errorList.filter(e => e.type === 'warning');
        return {
            total: this.errorList.length,
            errors: errors.length,
            warnings: warnings.length,
            currentIndex: this.currentErrorIndex
        };
    },

    /**
     * 更新状态栏错误计数
     */
    _updateErrorCount() {
        const stats = this.getErrorStats();
        const errorCountEl = document.getElementById('error-count');
        if (errorCountEl) {
            if (stats.total === 0) {
                errorCountEl.textContent = '';
                errorCountEl.className = '';
            } else {
                const parts = [];
                if (stats.errors > 0) parts.push(`❌ ${stats.errors}`);
                if (stats.warnings > 0) parts.push(`⚠️ ${stats.warnings}`);
                errorCountEl.textContent = parts.join(' ');
                errorCountEl.className = stats.errors > 0 ? 'has-errors' : 'has-warnings';
            }
        }
    },

    /**
     * 清除错误高亮（保留错误列表）
     */
    clearErrorHighlights() {
        if (!this.instance || this.errorDecorations.length === 0) return;
        
        this.instance.deltaDecorations(this.errorDecorations, []);
        this.errorDecorations = [];
    },

    /**
     * 清除所有错误（包括列表）
     */
    clearAllErrors() {
        this.clearErrorHighlights();
        this.errorList = [];
        this.currentErrorIndex = -1;
        this._updateErrorCount();
    },


    /**
     * 获取当前光标位置
     */
    getPosition() {
        return this.instance ? this.instance.getPosition() : { lineNumber: 1, column: 1 };
    },

    /**
     * 打开查找框 (Ctrl+F)
     */
    openFind() {
        if (this.instance) {
            this.instance.getAction('actions.find').run();
        }
    },

    /**
     * 打开查找替换框 (Ctrl+H)
     * 修复：使用正确的 action ID
     */
    openFindAndReplace() {
        if (this.instance) {
            // 修复：使用正确的 Monaco Editor action ID
            this.instance.getAction('editor.action.startFindReplaceAction').run();
        }
    },

    /**
     * 查找下一个
     */
    findNext() {
        if (this.instance) {
            this.instance.getAction('editor.action.nextMatchFindAction').run();
        }
    },

    /**
     * 查找上一个
     */
    findPrevious() {
        if (this.instance) {
            this.instance.getAction('editor.action.previousMatchFindAction').run();
        }
    },

    /**
     * 跳转到指定行 (Ctrl+G)
     */
    goToLine(lineNumber) {
        if (this.instance && lineNumber > 0) {
            this.instance.revealLineInCenter(lineNumber);
            this.instance.setPosition({ lineNumber: lineNumber, column: 1 });
            this.instance.focus();
        }
    },

    /**
     * 打开跳转到行对话框
     */
    openGoToLine() {
        if (this.instance) {
            this.instance.getAction('editor.action.gotoLine').run();
        }
    },

    /**
     * 格式化代码
     */
    formatDocument() {
        if (this.instance) {
            this.instance.getAction('editor.action.formatDocument').run();
        }
    },

    /**
     * 切换行号显示
     */
    toggleLineNumbers() {
        if (this.instance) {
            const current = this.instance.getOption(monaco.editor.EditorOption.lineNumbers);
            this.instance.updateOptions({
                lineNumbers: current === 'on' ? 'off' : 'on'
            });
        }
    },

    /**
     * 切换自动换行
     */
    toggleWordWrap() {
        if (this.instance) {
            const current = this.instance.getOption(monaco.editor.EditorOption.wordWrap);
            this.instance.updateOptions({
                wordWrap: current === 'on' ? 'off' : 'on'
            });
        }
    },

    /**
     * 切换 minimap
     */
    toggleMinimap() {
        if (this.instance) {
            const current = this.instance.getOption(monaco.editor.EditorOption.minimap);
            this.instance.updateOptions({
                minimap: { enabled: !current.enabled }
            });
        }
    },

    /**
     * 全选
     */
    selectAll() {
        if (this.instance) {
            this.instance.setSelection(this.instance.getModel().getFullModelRange());
        }
    },

    /**
     * 撤销
     */
    undo() {
        if (this.instance) {
            this.instance.trigger('keyboard', 'undo', null);
        }
    },

    /**
     * 重做
     */
    redo() {
        if (this.instance) {
            this.instance.trigger('keyboard', 'redo', null);
        }
    },

    /**
     * 解析HPL代码结构生成大纲
     */
    parseOutline() {
        if (!this.instance) return [];
        
        const content = this.instance.getValue();
        const lines = content.split('\n');
        const outline = [];
        
        let currentSection = null;
        let currentClass = null;
        let sectionStartLine = 0;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();
            const indent = line.match(/^(\s*)/)[1].length;
            
            // 检测节标题
            if (indent === 0 && trimmed.endsWith(':')) {
                const sectionName = trimmed.replace(':', '');
                currentSection = sectionName;
                sectionStartLine = i + 1;
                
                if (['classes', 'objects', 'includes', 'imports', 'main'].includes(sectionName)) {
                    outline.push({
                        type: 'section',
                        name: sectionName,
                        line: i + 1,
                        level: 0,
                        icon: this._getSectionIcon(sectionName)
                    });
                }
                continue;
            }
            
            // 在classes节中解析类定义
            if (currentSection === 'classes' && indent === 2 && trimmed.endsWith(':')) {
                const className = trimmed.replace(':', '');
                currentClass = className;
                
                outline.push({
                    type: 'class',
                    name: className,
                    line: i + 1,
                    level: 1,
                    icon: '⚙️',
                    parent: 'classes'
                });
                
                // 检查是否有parent
                const nextLine = lines[i + 1];
                if (nextLine && nextLine.trim().startsWith('parent:')) {
                    const parentMatch = nextLine.match(/parent:\s*(\w+)/);
                    if (parentMatch) {
                        outline[outline.length - 1].parentClass = parentMatch[1];
                    }
                }
                continue;
            }
            
            // 在类中解析方法
            if (currentSection === 'classes' && currentClass && indent === 4 && trimmed.includes(':')) {
                const methodMatch = trimmed.match(/^(\w+):\s*\(/);
                if (methodMatch) {
                    const methodName = methodMatch[1];
                    outline.push({
                        type: 'method',
                        name: methodName,
                        line: i + 1,
                        level: 2,
                        icon: '🔧',
                        parent: currentClass
                    });
                }
                continue;
            }
            
            // 在objects节中解析对象定义
            if (currentSection === 'objects' && indent === 2) {
                const objMatch = trimmed.match(/^(\w+):\s*(\w+)\(\)/);
                if (objMatch) {
                    const objName = objMatch[1];
                    const className = objMatch[2];
                    outline.push({
                        type: 'object',
                        name: objName,
                        className: className,
                        line: i + 1,
                        level: 1,
                        icon: '📦',
                        parent: 'objects'
                    });
                }
                continue;
            }
            
            // 在includes/imports节中解析包含/导入
            if ((currentSection === 'includes' || currentSection === 'imports') && indent === 2 && trimmed.startsWith('-')) {
                const itemName = trimmed.replace('-', '').trim();
                outline.push({
                    type: currentSection === 'includes' ? 'include' : 'import',
                    name: itemName,
                    line: i + 1,
                    level: 1,
                    icon: currentSection === 'includes' ? '📎' : '📥',
                    parent: currentSection
                });
                continue;
            }
            
            // 解析main函数
            if (currentSection === 'main' && indent === 0 && trimmed.startsWith('main:')) {
                outline.push({
                    type: 'function',
                    name: 'main',
                    line: i + 1,
                    level: 1,
                    icon: '▶️',
                    parent: 'main'
                });
                continue;
            }
        }
        
        return outline;
    },

    /**
     * 获取节的图标
     */
    _getSectionIcon(section) {
        const icons = {
            'classes': '🏗️',
            'objects': '📦',
            'includes': '📎',
            'imports': '📥',
            'main': '▶️'
        };
        return icons[section] || '📄';
    },

    /**
     * 渲染大纲视图
     */
    renderOutline() {
        const outline = this.parseOutline();
        const container = document.getElementById('outline-content');
        if (!container) return;
        
        if (outline.length === 0) {
            container.innerHTML = '<div class="outline-empty">打开文件以查看代码结构</div>';
            return;
        }
        
        container.innerHTML = '';
        
        outline.forEach(item => {
            const div = document.createElement('div');
            div.className = `outline-item level-${item.level} type-${item.type}`;
            div.dataset.line = item.line;
            
            let badge = '';
            if (item.type === 'object' && item.className) {
                badge = `<span class="outline-badge">${item.className}</span>`;
            } else if (item.type === 'class' && item.parentClass) {
                badge = `<span class="outline-badge">extends ${item.parentClass}</span>`;
            }
            
            div.innerHTML = `
                <span class="outline-icon">${item.icon}</span>
                <span class="outline-name">${item.name}</span>
                ${badge}
            `;
            
            div.addEventListener('click', () => {
                // 移除其他活动项
                container.querySelectorAll('.outline-item').forEach(el => el.classList.remove('active'));
                // 添加活动状态
                div.classList.add('active');
                // 跳转到对应行
                this.goToLine(item.line);
            });
            
            container.appendChild(div);
        });
    },

    /**
     * 更新大纲视图（带防抖）
     */
    updateOutline() {
        if (this._outlineTimeout) {
            clearTimeout(this._outlineTimeout);
        }
        this._outlineTimeout = setTimeout(() => {
            this.renderOutline();
        }, 500);
    },

    /**
     * 高亮当前光标位置对应的大纲项
     */
    highlightCurrentOutlineItem() {
        if (!this.instance) return;
        
        const position = this.getPosition();
        const outline = this.parseOutline();
        
        // 找到当前行所在的范围
        let currentItem = null;
        for (let i = outline.length - 1; i >= 0; i--) {
            if (outline[i].line <= position.lineNumber) {
                currentItem = outline[i];
                break;
            }
        }
        
        if (currentItem) {
            const container = document.getElementById('outline-content');
            if (container) {
                container.querySelectorAll('.outline-item').forEach(el => el.classList.remove('active'));
                const item = container.querySelector(`.outline-item[data-line="${currentItem.line}"]`);
                if (item) {
                    item.classList.add('active');
                    item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }
    }
};


// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLEditor;
}
