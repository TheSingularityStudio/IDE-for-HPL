HPL项目根目录/
├── hpl_runtime/           # 运行时目录
│   ├── models.py          # 数据模型定义（类、对象、函数、AST节点）
│   ├── lexer.py           # 词法分析器（Token生成）
│   ├── parser.py          # 顶层解析器（YAML解析、文件包含处理、模块导入解析）
│   ├── ast_parser.py      # AST解析器（语法分析，生成抽象语法树）
│   ├── evaluator.py       # 执行器（AST执行、表达式求值、模块函数调用）
│   ├── interpreter.py     # 主入口点（命令行接口）
│   ├── module_base.py     # 模块基类定义（HPLModule）
│   ├── module_loader.py   # 模块加载器（标准库模块加载）
│   └── stdlib/            # 标准库目录
│       ├── __init__.py    # 标准库包初始化
│       ├── io.py          # 文件IO操作模块
│       ├── json_mod.py    # JSON解析模块
│       ├── math.py        # 数学函数模块
│       ├── os_mod.py      # 操作系统接口模块
│       └── time_mod.py    # 日期时间处理模块
└── __init__.py         # 运行时包初始化