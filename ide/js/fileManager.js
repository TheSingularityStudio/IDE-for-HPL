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
    
    // 当前模式：'workspace' 或 'examples'
    currentMode: 'workspace',
    
    // 展开的文件夹集合
    expandedFolders: new Set(['workspace']),


    
    // 当前选中的文件树项
    selectedTreeItem: null,
    
    // 上下文菜单元素
    contextMenu: null,
    
    // 拖拽状态
    dragState: {
        isDragging: false,
        draggedItem: null,
        dropTarget: null
    },
    
    // 搜索状态
    searchState: {
        query: '',
        results: [],
        currentIndex: -1
    },
    
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
        this.initWorkspaceToggle();
    },

    /**
     * 初始化工作区/示例脚本切换功能
     * 现在通过面包屑导航的根元素切换
     */
    initWorkspaceToggle() {
        // 面包屑根元素点击事件在 HTML 中通过 onclick 绑定到 toggleMode()
        // 这里可以添加额外的初始化逻辑（如悬停提示等）
    },

    /**
     * 切换工作区/示例脚本模式（在两者之间切换）
     */
    toggleMode() {
        const newMode = this.currentMode === 'workspace' ? 'examples' : 'workspace';
        this.switchMode(newMode);
    },


    /**
     * 切换工作区/示例脚本模式
     */
    switchMode(mode) {
        if (this.currentMode === mode) return;
        
        this.currentMode = mode;
        
        // 更新面包屑工作区名称
        const workspaceName = document.querySelector('.breadcrumb-workspace-name');
        if (workspaceName) {
            const isWorkspace = mode === 'workspace';
            workspaceName.innerHTML = isWorkspace ? '💼 工作区' : '📚 示例脚本';
        }
        
        // 更新展开的文件夹
        this.expandedFolders = new Set([mode]);
        
        // 刷新文件树
        HPLApp.refreshFileTree();
        
        HPLUI.showOutput(`已切换到${mode === 'workspace' ? '工作区' : '示例脚本'}`, 'info');
    },



    /**
     * 获取当前模式的根目录
     */
    getCurrentRoot() {
        return this.currentMode;
    },

    /**
     * 检查当前是否在示例脚本模式
     */
    isExamplesMode() {
        return this.currentMode === 'examples';
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
        
        // 右键菜单 - 支持文件项和空白区域
        fileTree.addEventListener('contextmenu', (e) => {
            const item = e.target.closest('.file-item');
            if (item) {
                // 右键点击文件或文件夹
                e.preventDefault();
                this.selectTreeItem(item);
                this.showContextMenu(e.clientX, e.clientY, item);
            } else if (e.target.closest('.file-tree') || e.target.closest('.file-tree-empty')) {
                // 右键点击空白区域或空状态区域
                e.preventDefault();
                // 清除之前的选中状态
                document.querySelectorAll('.file-item.active').forEach(el => {
                    el.classList.remove('active');
                });
                this.selectedTreeItem = null;
            // 显示空白区域的上下文菜单，默认使用当前模式的根目录
            this.showContextMenu(e.clientX, e.clientY, null, this.currentMode);


            }
        });

        
        // 拖拽事件
        this.initDragAndDrop(fileTree);
        
        // 文件上传输入
        this.initFileUpload();
    },

    /**
     * 初始化拖拽功能
     */
    initDragAndDrop(fileTree) {
        // 拖拽开始
        fileTree.addEventListener('dragstart', (e) => {
            const item = e.target.closest('.file-item');
            if (!item) return;
            
            // 只允许文件拖拽
            if (item.classList.contains('folder')) return;
            
            this.dragState.isDragging = true;
            this.dragState.draggedItem = item;
            item.classList.add('dragging');
            
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', item.dataset.path);
        });
        
        // 拖拽经过
        fileTree.addEventListener('dragover', (e) => {
            e.preventDefault();
            const item = e.target.closest('.file-item');
            
            if (item && item.classList.contains('folder')) {
                item.classList.add('drag-over');
                this.dragState.dropTarget = item;
            }
        });
        
        // 拖拽离开
        fileTree.addEventListener('dragleave', (e) => {
            const item = e.target.closest('.file-item');
            if (item) {
                item.classList.remove('drag-over');
            }
        });
        
        // 放置
        fileTree.addEventListener('drop', async (e) => {
            e.preventDefault();
            const item = e.target.closest('.file-item');
            
            // 清理拖拽状态
            document.querySelectorAll('.file-item').forEach(el => {
                el.classList.remove('dragging', 'drag-over');
            });
            
            if (!item || !item.classList.contains('folder')) return;
            
            const sourcePath = e.dataTransfer.getData('text/plain');
            const targetPath = item.dataset.path;
            
            if (sourcePath && targetPath && sourcePath !== targetPath) {
                await this.moveItem(sourcePath, targetPath);
            }
            
            this.dragState.isDragging = false;
            this.dragState.draggedItem = null;
            this.dragState.dropTarget = null;
        });
        
        // 拖拽结束
        fileTree.addEventListener('dragend', () => {
            document.querySelectorAll('.file-item').forEach(el => {
                el.classList.remove('dragging', 'drag-over');
            });
            this.dragState.isDragging = false;
            this.dragState.draggedItem = null;
        });
    },

    /**
     * 初始化文件上传
     */
    initFileUpload() {
        // 创建隐藏的文件上传输入
        const uploadInput = document.createElement('input');
        uploadInput.type = 'file';
        uploadInput.id = 'file-upload-input';
        uploadInput.className = 'visually-hidden';
        uploadInput.multiple = true;
        document.body.appendChild(uploadInput);
        
        // 添加上传菜单项到上下文菜单
        const uploadMenuItem = document.createElement('div');
        uploadMenuItem.className = 'context-menu-item';
        uploadMenuItem.dataset.action = 'upload';
        uploadMenuItem.innerHTML = '📤 上传文件';
        this.contextMenu.insertBefore(uploadMenuItem, this.contextMenu.firstChild);
        
        // 处理文件选择
        uploadInput.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (!files.length) return;
            
            const targetPath = uploadInput.dataset.targetPath || this.currentMode;
            
            for (const file of files) {
                try {
                    const content = await this.readFileContent(file);
                    const fullPath = `${targetPath}/${file.name}`;
                    await HPLAPI.createFile(fullPath, content, this.currentMode);
                    HPLUI.showOutput(`✅ 已上传: ${file.name}`, 'success');
                } catch (error) {
                    HPLUI.showOutput(`上传失败 ${file.name}: ${error.message}`, 'error');
                }
            }
            
            HPLApp.refreshFileTree();
            uploadInput.value = '';
        });

    },

    /**
     * 读取文件内容
     */
    readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(new Error('读取文件失败'));
            reader.readAsText(file);
        });
    },

    /**
     * 移动文件到文件夹
     */
    async moveItem(sourcePath, targetFolder) {
        const filename = sourcePath.split('/').pop();
        const newPath = `${targetFolder}/${filename}`;
        
        try {
            await HPLAPI.renameItem(sourcePath, newPath, this.currentMode);
            HPLUI.showOutput(`✅ 已移动到: ${targetFolder}`, 'success');
            HPLApp.refreshFileTree();
        } catch (error) {
            HPLUI.showOutput('移动失败: ' + error.message, 'error');
        }
    },


    /**
     * 处理上传操作
     */
    handleUpload(targetPath) {
        const uploadInput = document.getElementById('file-upload-input');
        if (uploadInput) {
            // 处理根目录情况（targetPath为根目录名时）
            uploadInput.dataset.targetPath = targetPath || this.currentMode;
            uploadInput.click();
        }
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
     * @param {number} x - 菜单显示的X坐标
     * @param {number} y - 菜单显示的Y坐标
     * @param {HTMLElement|null} item - 右键点击的文件/文件夹元素，null表示空白区域
     * @param {string} defaultPath - 空白区域时的默认路径
     */
    showContextMenu(x, y, item, defaultPath = null) {
        const isFolder = item ? item.classList.contains('folder') : true; // 空白区域视为文件夹上下文
        const isEmptySpace = item === null;
        
        // 根据类型显示/隐藏菜单项
        const newFileItem = this.contextMenu.querySelector('[data-action="new-file"]');
        const newFolderItem = this.contextMenu.querySelector('[data-action="new-folder"]');
        const renameItem = this.contextMenu.querySelector('[data-action="rename"]');
        const deleteItem = this.contextMenu.querySelector('[data-action="delete"]');
        const uploadItem = this.contextMenu.querySelector('[data-action="upload"]');
        
        // 新建文件/文件夹：文件夹或空白区域显示
        if (newFileItem) newFileItem.style.display = isFolder ? 'block' : 'none';
        if (newFolderItem) newFolderItem.style.display = isFolder ? 'block' : 'none';
        
        // 重命名和删除：只在具体项目上显示，空白区域隐藏
        if (renameItem) renameItem.style.display = isEmptySpace ? 'none' : 'block';
        if (deleteItem) deleteItem.style.display = isEmptySpace ? 'none' : 'block';
        
        // 上传：文件夹或空白区域显示
        if (uploadItem) uploadItem.style.display = isFolder ? 'block' : 'none';
        
        // 存储默认路径（用于空白区域）
        this.contextMenu.dataset.defaultPath = defaultPath !== null ? defaultPath : (item ? item.dataset.path : this.currentMode);
        
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
        
        // 获取路径：优先使用选中项的路径，否则使用上下文菜单存储的默认路径
        let path;
        let isFolder;
        
        if (this.selectedTreeItem) {
            path = this.selectedTreeItem.dataset.path;
            isFolder = this.selectedTreeItem.classList.contains('folder');
        } else {
            // 空白区域右键时，使用默认路径（当前模式的根目录）
            path = this.contextMenu.dataset.defaultPath || this.currentMode;
            isFolder = true; // 默认视为文件夹上下文
        }
        
        switch (action) {

            case 'upload':
                if (isFolder) this.handleUpload(path);
                break;
            case 'new-file':
                if (isFolder) this.createNewFile(path);
                break;
            case 'new-folder':
                if (isFolder) this.createNewFolder(path);
                break;
            case 'rename':
                if (this.selectedTreeItem) this.renameItem(path, isFolder);
                break;
            case 'delete':
                if (this.selectedTreeItem) this.deleteItem(path, isFolder);
                break;
            case 'refresh':
                HPLApp.refreshFileTree();
                break;
        }
    },


    /**
     * 搜索文件
     */
    searchFiles(query) {
        if (!query) {
            this.searchState.results = [];
            this.searchState.currentIndex = -1;
            this.renderFileTree();
            return;
        }
        
        this.searchState.query = query.toLowerCase();
        this.searchState.results = [];
        
        const searchInTree = (node) => {
            if (node.name.toLowerCase().includes(this.searchState.query)) {
                this.searchState.results.push(node.path);
            }
            
            if (node.children) {
                node.children.forEach(child => searchInTree(child));
            }
        };
        
        if (this.fileTreeData) {
            searchInTree(this.fileTreeData);
        }
        
        // 高亮搜索结果
        this.highlightSearchResults();
        
        return this.searchState.results;
    },

    /**
     * 高亮搜索结果
     */
    highlightSearchResults() {
        document.querySelectorAll('.file-item').forEach(item => {
            const path = item.dataset.path;
            const name = item.querySelector('.file-name');
            
            if (this.searchState.results.includes(path)) {
                item.classList.add('search-match');
                // 展开包含搜索结果的文件夹
                const parentFolder = item.closest('.file-item.folder');
                if (parentFolder) {
                    const parentPath = parentFolder.dataset.path;
                    this.expandedFolders.add(parentPath);
                }
            } else {
                item.classList.remove('search-match');
            }
        });
    },

    /**
     * 清除搜索
     */
    clearSearch() {
        this.searchState.query = '';
        this.searchState.results = [];
        this.searchState.currentIndex = -1;
        document.querySelectorAll('.file-item').forEach(item => {
            item.classList.remove('search-match');
        });
    },


    /**
     * 创建新文件
     */
    async createNewFile(folderPath) {
        let filename = prompt('请输入文件名（包含扩展名）：', 'new_file.hpl');
        if (!filename) return;
        
        // 自动添加 .hpl 扩展名
        if (!filename.includes('.')) {
            filename += '.hpl';
        }
        
        if (!HPLUtils.isValidFilename(filename)) {
            HPLUI.showOutput('错误：文件名无效', 'error');
            return;
        }
        
        // 确保是 .hpl 文件
        if (!filename.endsWith('.hpl')) {
            HPLUI.showOutput('错误：请创建 .hpl 文件', 'error');
            return;
        }
        
        // 处理路径：API需要相对于模式根目录的路径（不包含workspace/前缀）
        let relativePath;
        if (!folderPath || folderPath === this.currentMode) {
            // 在根目录创建，直接使用文件名
            relativePath = filename;
        } else if (folderPath.startsWith(this.currentMode + '/')) {
            // 完整路径包含模式前缀，去掉前缀后拼接
            const subPath = folderPath.substring(this.currentMode.length + 1);
            relativePath = subPath ? `${subPath}/${filename}` : filename;
        } else {
            // 其他情况，假设是相对路径
            relativePath = `${folderPath}/${filename}`;
        }
        
        try {
            // 检查文件是否已存在
            const tree = this.fileTreeData;
            const checkExists = (node, targetName) => {
                if (node.children) {
                    for (const child of node.children) {
                        if (child.name === targetName && child.type === 'file') {
                            return true;
                        }
                        if (child.children && checkExists(child, targetName)) {
                            return true;
                        }
                    }
                }
                return false;
            };
            
            const targetFolder = (!folderPath || folderPath === this.currentMode) ? tree : 
                this.findNodeInTree(tree, folderPath);
            
            if (targetFolder && checkExists(targetFolder, filename)) {
                const overwrite = confirm(`文件 "${filename}" 已存在，是否覆盖？`);
                if (!overwrite) return;
            }
            
            await HPLAPI.createFile(relativePath, this.DEFAULT_CONTENT, this.currentMode);

            HPLUI.showOutput(`✅ 文件已创建: ${filename}`, 'success');
            
            // 先刷新文件树，等待完成
            await HPLApp.refreshFileTree();
            
            // 展开父文件夹
            if (folderPath && folderPath !== this.currentMode) {
                this.expandedFolders.add(folderPath);
                this.renderFileTree();
            }
            
            // 使用正确的文件打开方式
            this.openFileInEditor(relativePath, this.DEFAULT_CONTENT, true);
        } catch (error) {
            HPLUI.showOutput('创建文件失败: ' + error.message, 'error');
        }
    },


    /**
     * 在文件树中查找节点
     */
    findNodeInTree(tree, path) {
        if (tree.path === path) return tree;
        if (tree.children) {
            for (const child of tree.children) {
                const found = this.findNodeInTree(child, path);
                if (found) return found;
            }
        }
        return null;
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
        
        // 处理根目录情况（parentPath为根目录名时）
        const fullPath = parentPath === this.currentMode ? `${parentPath}/${folderName}` :
                        (parentPath ? `${parentPath}/${folderName}` : folderName);
        
        try {
            await HPLAPI.createFolder(fullPath, this.currentMode);

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
            await HPLAPI.renameItem(path, newPath, this.currentMode);
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
            await HPLAPI.deleteItem(path, this.currentMode);
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
        
        // 检查是否为空
        if (!data.children || data.children.length === 0) {
            this.renderEmptyState(fileTree);
            return;
        }
        
        // 不显示根节点（workspace/examples），直接渲染其子项
        data.children.forEach(child => {
            this.renderTreeNode(fileTree, child, 0);
        });
        
        // 如果有搜索结果，高亮它们
        if (this.searchState.results.length > 0) {
            this.highlightSearchResults();
        }
    },


    /**
     * 渲染空状态
     */
    renderEmptyState(container) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'file-tree-empty';
        emptyDiv.innerHTML = `
            <div class="empty-icon">📂</div>
            <div class="empty-text">文件夹为空</div>
            <div class="empty-hint">右键点击创建新文件或文件夹</div>
        `;
        container.appendChild(emptyDiv);
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
                <span class="file-name" title="${HPLUtils.escapeHtml(node.path)}">${HPLUtils.escapeHtml(node.name)}</span>
            `;
            
            // 添加拖拽属性
            item.draggable = false;
            
            container.appendChild(item);
            
            // 递归渲染子项
            if (isExpanded && node.children) {
                if (node.children.length === 0) {
                    // 空文件夹提示
                    const emptyHint = document.createElement('div');
                    emptyHint.className = 'file-item empty-hint';
                    emptyHint.style.paddingLeft = `${12 + (level + 1) * 16}px`;
                    emptyHint.innerHTML = '<span class="file-name" style="color: var(--text-secondary); font-style: italic;">(空文件夹)</span>';
                    container.appendChild(emptyHint);
                } else {
                    node.children.forEach(child => {
                        this.renderTreeNode(container, child, level + 1);
                    });
                }
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
                'yml': '⚙️',
                'js': '📜',
                'css': '🎨',
                'html': '🌐',
                'xml': '📰',
                'csv': '📊',
                'jpg': '🖼️',
                'jpeg': '🖼️',
                'png': '🖼️',
                'gif': '🖼️',
                'svg': '🎭'
            };
            const icon = iconMap[ext] || '📄';
            
            item.innerHTML = `
                <span class="file-icon">${icon}</span>
                <span class="file-name" title="${HPLUtils.escapeHtml(node.path)}">${HPLUtils.escapeHtml(node.name)}</span>
            `;
            
            // 高亮当前打开的文件
            if (this.currentFile === node.name) {
                item.classList.add('active');
            }
            
            // 添加拖拽属性
            item.draggable = true;
            
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
