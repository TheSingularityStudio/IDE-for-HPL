# HPL IDE

HPL（H Programming Language）集成开发环境

## 功能特性

- 📝 **专业代码编辑器** - 基于 Monaco Editor（VS Code 同款编辑器）
- 🎨 **语法高亮** - 完整的 HPL 语法支持
- 🔮 **智能补全** - 关键字、内置函数、标准库自动补全
- 📁 **文件管理** - 新建、打开、保存 HPL 文件
- 🏃 **代码执行** - 一键运行 HPL 程序
- 📤 **输出控制台** - 实时显示程序输出和错误信息
- 📂 **示例浏览** - 快速打开示例文件

## 快速开始

### 1. 安装依赖

```bash
pip install flask flask-cors
```

### 2. 启动后端服务器

```bash
cd ide
python server.py
```

服务器将在 http://localhost:5000 运行

### 3. 打开 IDE

直接用浏览器打开 `ide/index.html` 文件，或使用本地服务器：

```bash
# 使用 Python 启动简单 HTTP 服务器
cd ide
python -m http.server 8080
```

然后访问 http://localhost:8080

## 使用说明

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+N` | 新建文件 |
| `Ctrl+O` | 打开文件 |
| `Ctrl+S` | 保存文件 |
| `F5` | 运行程序 |

### 界面说明

1. **工具栏** - 新建、打开、保存、运行按钮
2. **文件资源管理器** - 浏览示例文件
3. **编辑器** - 编写 HPL 代码
4. **标签页** - 管理打开的文件
5. **输出面板** - 显示程序输出
6. **状态栏** - 显示光标位置和文件信息

### 运行代码

1. 编写或打开 HPL 代码
2. 点击工具栏的 **▶️ 运行** 按钮或按 `F5`
3. 在底部输出面板查看结果

## 项目结构

```
ide/
├── index.html      # 主界面
├── css/
│   └── style.css   # 样式表
├── js/
│   └── app.js      # 前端应用
├── server.py       # 后端服务器
└── README.md       # 本文件
```

## 技术栈

- **前端**: HTML5, CSS3, JavaScript, Monaco Editor
- **后端**: Python, Flask
- **运行时**: HPL Runtime (Python)

## 注意事项

1. 必须先启动后端服务器才能执行代码
2. 后端服务器默认运行在 5000 端口
3. 前端可以通过文件协议或 HTTP 服务器打开

## 许可证

MIT License
