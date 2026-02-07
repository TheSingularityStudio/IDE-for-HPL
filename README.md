# IDE-for-HPL

HPL（H Programming Language）专用的集成开发环境，基于 Web 的 IDE，提供代码编辑、运行和调试功能。

## 功能特性

- 📝 **代码编辑**：基于 Monaco Editor，支持语法高亮、自动补全
- 🚀 **代码运行**：一键运行 HPL 代码，实时查看输出
- 📁 **文件管理**：支持新建、打开、保存 HPL 文件
- 📂 **示例浏览**：内置示例文件浏览器
- ⚙️ **可配置**：支持自定义后端服务器地址、主题、字体大小等
- 🔒 **安全执行**：后端支持超时限制、请求大小限制

## 前置依赖

本项目需要 `hpl-runtime` 作为外部依赖来执行 HPL 代码。

```bash
# 安装 hpl-runtime
pip install hpl-runtime
```

## 安装与运行

### 1. 克隆项目

```bash
git clone https://github.com/TheSingularityStudio/IDE-for-HPL.git
cd IDE-for-HPL
```

### 2. 安装依赖

```bash
# 安装 Flask 和 flask-cors
pip install flask flask-cors
```

### 3. 启动后端服务器

```bash
cd ide
python server.py
```

服务器将运行在 `http://localhost:5000`

### 4. 打开 IDE

在浏览器中访问 `http://localhost:5000` 即可使用 IDE。

## 项目结构

```
IDE-for-HPL/
├── ide/                    # IDE 主目录
│   ├── server.py           # Flask 后端服务器
│   ├── index.html          # IDE 主页面
│   ├── css/
│   │   └── style.css       # 样式文件
│   └── js/
│       ├── app.js          # 主应用逻辑
│       └── config.js       # 配置管理
├── examples/               # 示例 HPL 文件
│   ├── example.hpl
│   ├── base.hpl
│   └── ...
├── docs/                   # 文档
│   ├── HPL语法手册.md
│   └── hpl-runtime架构.md
└── README.md
```

## 使用说明

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+N` | 新建文件 |
| `Ctrl+O` | 打开文件 |
| `Ctrl+S` | 保存文件 |
| `Ctrl+,` | 打开设置 |
| `F5` | 运行程序 |
| `ESC` | 关闭对话框 |

### 配置说明

点击工具栏的 **⚙️ 设置** 按钮，可以配置：

- **后端服务器地址**：默认为 `http://localhost:5000`
- **请求超时**：默认为 30000 毫秒（30秒）
- **编辑器字体大小**：默认为 14px
- **编辑器主题**：深色/浅色/高对比度

### 运行代码

1. 在编辑器中编写 HPL 代码
2. 点击 **▶️ 运行** 按钮或按 `F5`
3. 在底部 **输出** 面板查看运行结果

## 浏览器兼容性

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+

## 安全特性

后端服务器实现了以下安全特性：

- ⏱️ **执行超时限制**：默认 5 秒
- 📦 **请求大小限制**：最大 1MB
- 🛡️ **路径遍历防护**：防止目录遍历攻击
- 🧹 **自动清理**：临时文件自动清理

## 技术栈

- **前端**：HTML5, CSS3, JavaScript, Monaco Editor
- **后端**：Python, Flask, Flask-CORS
- **语言支持**：HPL (H Programming Language)

## 许可证

[LICENSE](LICENSE)
