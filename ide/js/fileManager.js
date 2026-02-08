/**
 * HPL IDE - 文件管理模块
 * 管理文件操作、标签页、自动保存、文件树
 */

const HPLFileManager = {
    // 当前打开的文件
    currentFile: null,
    
    // 打开的文件集合
    openFiles: new Map(),
    
    // 自动保存定时器
    autoSaveInterval: null,
    
    // 文件树数据
    fileTreeData: null,
    
    // 展开的文件夹集合
    expandedFolders: new Set(['examples']),
    
    // 当前选中的文件树项
    selectedTreeItem: null,
    
    // 上下文菜单元素
    contextMenu: null,
    
    // 默认文件名
    DEFAULT_FILENAME: 'untitled.hpl',
    
    // 新文件默认内容
    DEFAULT_CONTENT: `classes:
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
`,


    /**
     * 初始化文件管理器
     */
    init() {
        this.initAutoSave();
        this.initContextMenu();
        this.initFileTreeEvents();
    },

    /**
     * 初始化上下文菜单
     */
    initContextMenu() {
        // 创建上下文菜单元素
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'context-menu hidden';
        this.contextMenu.innerHTML = `
            <div class="context-menu-item" data-action="new-file">📄 新建文件</div>
            <div class="context-menu-item" data-action="new-folder">📁 新建文件夹</div>
            <div class="context-menu-separator"></div>
            <div class="context-menu-item" data-action="rename">✏️ 重命名</div>
            <div class="context-menu-item" data-action="delete">🗑️ 删除</div>
            <div class="context-menu-separator"></div>
            <div class="context-menu-item" data-action="refresh">🔄 刷新</div>
        `;
        document.body.appendChild(this.contextMenu);
        
        // 绑定菜单项点击事件
        this.contextMenu.addEventListener('click', (e) => {
            const item = e.target.closest('.context-menu-item');
            if (item) {
                this.handleContextMenuAction(item.dataset.action);
            }
        });
        
        // 点击其他地方关闭菜单
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.context-menu')) {
                this.hideContextMenu();
            }
        });
    },

    /**
     * 初始化文件树事件
     */
    initFileTreeEvents() {
        const fileTree = document.getElementById('file-tree');
        if (!fileTree) return;
        
        // 点击事件处理
        fileTree.addEventListener('click', (e) => {
            const item = e.target.closest('.file-item');
            if (!item) return;
            
            const path = item.dataset.path;
            const isFolder = item.classList.contains('folder');
            
            // 更新选中状态
            this.selectTreeItem(item);
            
            if (isFolder) {
                // 切换文件夹展开/折叠
                this.toggleFolder(path);
            } else {
                // 打开文件
                const filename = path.split('/').pop();
                HPLApp.loadExample(filename);
            }
        });
        
        // 右键菜单
        fileTree.addEventListener('contextmenu', (e) => {
            const item = e.target.closest('.file-item');
            if (item) {
                e.preventDefault();
                this.selectTreeItem(item);
                this.showContextMenu(e.clientX, e.clientY, item);
            }
        });
    },

    /**
     * 选中文件树项
     */
    selectTreeItem(item) {
        // 移除之前的选中状态
        document.querySelectorAll('.file-item.active').forEach(el => {
            el.classList.remove('active');
        });
        
        // 添加新的选中状态
        item.classList.add('active');
        this.selectedTreeItem = item;
    },

    /**
     * 切换文件夹展开/折叠
     */
    toggleFolder(path) {
        const item = document.querySelector(`.file-item[data-path="${CSS.escape(path)}"]`);
        if (!item || !item.classList.contains('folder')) return;
        
        if (this.expandedFolders.has(path)) {
            this.expandedFolders.delete(path);
            item.classList.remove('expanded');
        } else {
            this.expandedFolders.add(path);
            item.classList.add('expanded');
        }
        
        // 重新渲染文件树
        this.renderFileTree();
    },

    /**
     * 显示上下文菜单
     */
    showContextMenu(x, y, item) {
        const isFolder = item.classList.contains('folder');
        
        // 根据类型显示/隐藏菜单项
        const newFileItem = this.contextMenu.querySelector('[data-action="new-file"]');
        const newFolderItem = this.contextMenu.querySelector('[data-action="new-folder"]');
        
        if (newFileItem) newFileItem.style.display = isFolder ? 'block' : 'none';
        if (newFolderItem) newFolderItem.style.display = isFolder ? 'block' : 'none';
        
        // 定位菜单
        this.contextMenu.style.left = `${x}px`;
        this.contextMenu.style.top = `${y}px`;
        this.contextMenu.classList.remove('hidden');
    },

    /**
     * 隐藏上下文菜单
     */
    hideContextMenu() {
        this.contextMenu.classList.add('hidden');
    },

    /**
     * 处理上下文菜单操作
     */
    handleContextMenuAction(action) {
        this.hideContextMenu();
        
        if (!this.selectedTreeItem) return;
        
        const path = this.selectedTreeItem.dataset.path;
        const isFolder = this.selectedTreeItem.classList.contains('folder');
        
        switch (action) {
            case 'new-file':
                if (isFolder) this.createNewFile(path);
                break;
            case 'new-folder':
                if (isFolder) this.createNewFolder(path);
                break;
            case 'rename':
                this.renameItem(path, isFolder);
                break;
            case 'delete':
                this.deleteItem(path, isFolder);
                break;
            case 'refresh':
                HPLApp.refreshFileTree();
                break;
        }
    },

    /**
     * 创建新文件
     */
    async createNewFile(folderPath) {
        const filename = prompt('请输入文件名（包含扩展名）：', 'new_file.hpl');
        if (!filename) return;
        
        if (!HPLUtils.isValidFilename(filename)) {
            HPLUI.showOutput('错误：文件名无效', 'error');
            return;
        }
        
        const fullPath = `${folderPath}/${filename}`;
        
        try {
            await HPLAPI.createFile(fullPath, '');
            HPLUI.showOutput(`✅ 文件已创建: ${filename}`, 'success');
            HPLApp.refreshFileTree();
            
            // 自动打开新文件
            HPLApp.loadExample(filename);
        } catch (error) {
            HPLUI.showOutput('创建文件失败: ' + error.message, 'error');
        }
    },

    /**
     * 创建新文件夹
     */
    async createNewFolder(parentPath) {
        const folderName = prompt('请输入文件夹名称：', 'new_folder');
        if (!folderName) return;
        
        if (!HPLUtils.isValidFilename(folderName)) {
            HPLUI.showOutput('错误：文件夹名称无效', 'error');
            return;
        }
        
        const fullPath = `${parentPath}/${folderName}`;
        
        try {
            await HPLAPI.createFolder(fullPath);
            HPLUI.showOutput(`✅ 文件夹已创建: ${folderName}`, 'success');
            
            // 自动展开父文件夹
            this.expandedFolders.add(parentPath);
            HPLApp.refreshFileTree();
        } catch (error) {
            HPLUI.showOutput('创建文件夹失败: ' + error.message, 'error');
        }
    },

    /**
     * 重命名文件或文件夹
     */
    async renameItem(path, isFolder) {
        const oldName = path.split('/').pop();
        const newName = prompt(`请输入新名称：`, oldName);
        if (!newName || newName === oldName) return;
        
        if (!HPLUtils.isValidFilename(newName)) {
            HPLUI.showOutput('错误：名称无效', 'error');
            return;
        }
        
        const parentPath = path.substring(0, path.lastIndexOf('/'));
        const newPath = parentPath ? `${parentPath}/${newName}` : newName;
        
        try {
            await HPLAPI.renameItem(path, newPath);
            HPLUI.showOutput(`✅ 已重命名为: ${newName}`, 'success');
            HPLApp.refreshFileTree();
        } catch (error) {
            HPLUI.showOutput('重命名失败: ' + error.message, 'error');
        }
    },

    /**
     * 删除文件或文件夹
     */
    async deleteItem(path, isFolder) {
        const itemType = isFolder ? '文件夹' : '文件';
        const itemName = path.split('/').pop();
        
        if (!confirm(`确定要删除${itemType} "${itemName}" 吗？${isFolder ? '文件夹中的所有内容都将被删除！' : ''}`)) {
            return;
        }
        
        try {
            await HPLAPI.deleteItem(path);
            HPLUI.showOutput(`✅ ${itemType}已删除: ${itemName}`, 'success');
            HPLApp.refreshFileTree();
        } catch (error) {
            HPLUI.showOutput('删除失败: ' + error.message, 'error');
        }
    },

    /**
     * 渲染文件树
     */
    renderFileTree(data = this.fileTreeData) {
        const fileTree = document.getElementById('file-tree');
        if (!fileTree || !data) return;
        
        fileTree.innerHTML = '';
        this.renderTreeNode(fileTree, data, 0);
    },

    /**
     * 递归渲染树节点
     */
    renderTreeNode(container, node, level) {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.dataset.path = node.path;
        item.style.paddingLeft = `${12 + level * 16}px`;
        
        // 判断是否为文件夹
        const isFolder = node.type === 'folder' || (node.children && node.children.length > 0);
        
        if (isFolder) {
            item.classList.add('folder');
            if (this.expandedFolders.has(node.path)) {
                item.classList.add('expanded');
            }
            
            const isExpanded = this.expandedFolders.has(node.path);
            const icon = isExpanded ? '📂' : '📁';
            
            item.innerHTML = `
                <span class="file-icon folder-icon">${icon}</span>
                <span class="file-name">${HPLUtils.escapeHtml(node.name)}</span>
            `;
            
            container.appendChild(item);
            
            // 递归渲染子项
            if (isExpanded && node.children) {
                node.children.forEach(child => {
                    this.renderTreeNode(container, child, level + 1);
                });
            }
        } else {
            item.classList.add('file');
            
            // 根据文件扩展名选择图标
            const ext = node.name.split('.').pop().toLowerCase();
            const iconMap = {
                'hpl': '📄',
                'py': '🐍',
                'md': '📝',
                'txt': '📃',
                'json': '📋',
                'yaml': '⚙️',
                'yml': '⚙️'
            };
            const icon = iconMap[ext] || '📄';
            
            item.innerHTML = `
                <span class="file-icon">${icon}</span>
                <span class="file-name">${HPLUtils.escapeHtml(node.name)}</span>
            `;
            
            // 高亮当前打开的文件
            if (this.currentFile === node.name) {
                item.classList.add('active');
            }
            
            container.appendChild(item);
        }
    },

    /**
     * 设置文件树数据
     */
    setFileTreeData(data) {
        this.fileTreeData = data;
        this.renderFileTree();
    },


    /**
     * 初始化自动保存
     */
    initAutoSave() {
        // 清除现有的自动保存定时器
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
            this.autoSaveInterval = null;
        }
        
        const config = HPLConfig.getConfig();
        if (!config.autoSave) return;
        
        // 设置新的自动保存定时器
        this.autoSaveInterval = setInterval(() => {
            if (this.currentFile && this.openFiles.get(this.currentFile)?.isModified) {
                this.autoSaveCurrentFile();
            }
        }, config.autoSaveInterval || 5000);
    },

    /**
     * 自动保存当前文件
     */
    autoSaveCurrentFile() {
        const content = HPLEditor.getValue();
        const fileData = this.openFiles.get(this.currentFile);
        if (!fileData) return;
        
        try {
            const autoSaveKey = `hpl-autosave-${this.currentFile}`;
            localStorage.setItem(autoSaveKey, JSON.stringify({
                content: content,
                timestamp: Date.now(),
                file: this.currentFile
            }));
            
            console.log(`自动保存: ${this.currentFile}`);
            HPLUI.showAutoSaveIndicator();
        } catch (e) {
            console.error('自动保存失败:', e);
        }
    },

    /**
     * 恢复自动保存的内容
     */
    restoreAutoSavedContent(filename) {
        try {
            const autoSaveKey = `hpl-autosave-${filename}`;
            const saved = localStorage.getItem(autoSaveKey);
            if (saved) {
                const data = JSON.parse(saved);
                if (data.content && data.timestamp) {
                    const age = Date.now() - data.timestamp;
                    const ageMinutes = Math.floor(age / 60000);
                    console.log(`找到自动保存的内容: ${filename} (${ageMinutes}分钟前)`);
                    return data.content;
                }
            }
        } catch (e) {
            console.error('恢复自动保存内容失败:', e);
        }
        return null;
    },

    /**
     * 新建文件
     */
    newFile() {
        this.openFileInEditor(this.DEFAULT_FILENAME, this.DEFAULT_CONTENT, true);
    },

    /**
     * 打开文件（从文件选择器）
     */
    openFromFileInput(file) {
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            this.openFileInEditor(file.name, e.target.result, false);
        };
        reader.onerror = (e) => {
            HPLUI.showOutput('读取文件失败: ' + (e.target.error?.message || '未知错误'), 'error');
        };
        reader.readAsText(file);
    },

    /**
     * 保存当前文件
     */
    saveCurrentFile() {
        if (!this.currentFile) {
            HPLUI.showSaveDialog(this.DEFAULT_FILENAME);
            return;
        }
        
        const content = HPLEditor.getValue();
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        let a = null;
        try {
            a = document.createElement('a');
            a.href = url;
            a.download = this.currentFile.replace('*', '');
            document.body.appendChild(a);
            a.click();
            
            this.markFileAsModified(this.currentFile, false);
            HPLUI.showOutput('文件已保存: ' + this.currentFile.replace('*', ''), 'success');
        } catch (error) {
            HPLUI.showOutput('保存文件失败: ' + error.message, 'error');
        } finally {
            if (a && a.parentNode) {
                a.parentNode.removeChild(a);
            }
            URL.revokeObjectURL(url);
        }
    },

    /**
     * 确认保存（从对话框）
     */
    confirmSave(filename) {
        if (!filename || !HPLUtils.isValidFilename(filename)) {
            HPLUI.showOutput('错误: 文件名无效', 'error');
            return;
        }
        
        // 确保文件名有扩展名
        const finalFilename = filename.endsWith('.hpl') ? filename : filename + '.hpl';
        
        this.openFileInEditor(finalFilename, HPLEditor.getValue(), true);
        HPLUI.hideSaveDialog();
        this.saveCurrentFile();
    },

    /**
     * 在编辑器中打开文件
     */
    openFileInEditor(filename, content, isNew = false) {
        // 检查是否已打开
        if (this.openFiles.has(filename)) {
            this.switchToFile(filename);
            return;
        }
        
        const displayName = isNew ? filename + '*' : filename;
        this.openFiles.set(filename, {
            content: content,
            isModified: isNew,
            isNew: isNew
        });
        
        // 创建标签页
        this.createTab(filename, displayName);
        
        // 切换到新文件
        this.switchToFile(filename);
        
        // 更新文件信息
        HPLUI.updateFileInfo(filename, isNew);
    },

    /**
     * 创建标签页
     */
    createTab(filename, displayName) {
        const tabsContainer = document.getElementById('tabs-container');
        if (!tabsContainer) return;
        
        const tab = HPLUI.createTabElement(filename, displayName);
        
        // 点击切换
        tab.addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-close')) {
                this.closeFile(filename);
            } else {
                this.switchToFile(filename);
            }
        });
        
        tabsContainer.appendChild(tab);
    },

    /**
     * 切换到指定文件
     */
    switchToFile(filename) {
        // 更新标签页状态
        HPLUI.switchTab(filename);
        
        // 保存当前文件内容
        if (this.currentFile) {
            const fileData = this.openFiles.get(this.currentFile);
            if (fileData) {
                fileData.content = HPLEditor.getValue();
            }
        }
        
        // 切换文件
        this.currentFile = filename;
        const fileData = this.openFiles.get(filename);
        
        if (fileData) {
            HPLEditor.setValue(fileData.content);
            HPLEditor.focus();
        }
        
        // 更新文件信息
        HPLUI.updateFileInfo(filename, fileData?.isModified);
        
        // 隐藏欢迎页面
        HPLUI.hideWelcomePage();
    },

    /**
     * 关闭文件
     */
    closeFile(filename) {
        const fileData = this.openFiles.get(filename);
        
        // 如果有修改，提示保存
        if (fileData?.isModified) {
            if (!confirm(`文件 ${filename} 有未保存的更改，确定要关闭吗？`)) {
                return;
            }
        }
        
        this.openFiles.delete(filename);
        
        // 移除标签页
        HPLUI.removeTab(filename);
        
        // 如果关闭的是当前文件，切换到其他文件
        if (this.currentFile === filename) {
            const remainingFiles = Array.from(this.openFiles.keys());
            if (remainingFiles.length > 0) {
                this.switchToFile(remainingFiles[0]);
            } else {
                this.currentFile = null;
                HPLEditor.setValue('');
                HPLUI.showWelcomePage();
                HPLUI.updateFileInfo('未选择文件', false);
            }
        }
    },

    /**
     * 标记文件为已修改/未修改
     */
    markFileAsModified(filename, modified) {
        const fileData = this.openFiles.get(filename);
        if (!fileData) return;
        
        fileData.isModified = modified;
        
        // 更新标签页标题
        HPLUI.updateTabTitle(filename, modified);
        
        // 更新文件信息
        HPLUI.updateFileInfo(filename, modified);
    },

    /**
     * 标记当前文件为已修改
     */
    markCurrentFileAsModified() {
        if (this.currentFile) {
            this.markFileAsModified(this.currentFile, true);
        }
    },

    /**
     * 获取当前文件
     */
    getCurrentFile() {
        return this.currentFile;
    },

    /**
     * 获取当前文件内容
     */
    getCurrentFileContent() {
        return HPLEditor.getValue();
    },

    /**
     * 检查是否有文件打开
     */
    hasOpenFiles() {
        return this.openFiles.size > 0;
    },

    /**
     * 获取打开的文件列表
     */
    getOpenFiles() {
        return Array.from(this.openFiles.keys());
    },

    /**
     * 高亮文件树中的文件
     */
    highlightFileInTree(filename) {
        document.querySelectorAll('.file-item.file').forEach(item => {
            const path = item.dataset.path;
            const itemFilename = path ? path.split('/').pop() : '';
            if (itemFilename === filename) {
                this.selectTreeItem(item);
            }
        });
    }
};


// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLFileManager;
}
