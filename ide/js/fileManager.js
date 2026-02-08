/**
 * HPL IDE - 文件管理模块
 * 管理文件操作、标签页、自动保存
 */

const HPLFileManager = {
    // 当前打开的文件
    currentFile: null,
    
    // 打开的文件集合
    openFiles: new Map(),
    
    // 自动保存定时器
    autoSaveInterval: null,
    
    // 追踪创建的 blob URL 用于清理
    _blobUrls: new Set(),
    
    // 自动保存配置
    AUTO_SAVE_CONFIG: {
        MAX_SIZE: 1024 * 1024, // 1MB 最大自动保存大小
        MAX_ENTRIES: 10, // 最多保留 10 个自动保存文件
        MAX_AGE: 7 * 24 * 60 * 60 * 1000 // 7 天最大保留时间
    },

    
    // 默认文件名
    DEFAULT_FILENAME: 'untitled.hpl',
    
    // 最近文件存储键
    RECENT_FILES_KEY: 'hpl-recent-files',
    
    // 最大最近文件数
    MAX_RECENT_FILES: 10,

    
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
    },

    /**
     * 获取最近文件列表
     */
    getRecentFiles() {
        try {
            const stored = localStorage.getItem(this.RECENT_FILES_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('获取最近文件失败:', e);
            return [];
        }
    },

    /**
     * 添加文件到最近文件列表
     */
    addToRecentFiles(filename) {
        if (!filename || filename === this.DEFAULT_FILENAME) return;
        
        try {
            let recentFiles = this.getRecentFiles();
            
            // 移除已存在的相同文件
            recentFiles = recentFiles.filter(f => f !== filename);
            
            // 添加到开头
            recentFiles.unshift(filename);
            
            // 限制数量
            if (recentFiles.length > this.MAX_RECENT_FILES) {
                recentFiles = recentFiles.slice(0, this.MAX_RECENT_FILES);
            }
            
            localStorage.setItem(this.RECENT_FILES_KEY, JSON.stringify(recentFiles));
        } catch (e) {
            console.error('添加最近文件失败:', e);
        }
    },

    /**
     * 清空最近文件列表
     */
    clearRecentFiles() {
        try {
            localStorage.removeItem(this.RECENT_FILES_KEY);
        } catch (e) {
            console.error('清空最近文件失败:', e);
        }
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
     * 检查内容大小是否适合自动保存
     */
    _isValidAutoSaveSize(content) {
        const size = new Blob([content]).size;
        return size <= this.AUTO_SAVE_CONFIG.MAX_SIZE;
    },

    /**
     * 清理旧的自动保存条目
     */
    _cleanupOldAutoSaves() {
        try {
            const autoSaves = [];
            
            // 收集所有自动保存条目
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith('hpl-autosave-')) {
                    try {
                        const data = JSON.parse(localStorage.getItem(key));
                        if (data && data.timestamp) {
                            autoSaves.push({ key, timestamp: data.timestamp });
                        }
                    } catch (e) {
                        // 无效的条目，删除
                        localStorage.removeItem(key);
                    }
                }
            }
            
            // 按时间排序
            autoSaves.sort((a, b) => a.timestamp - b.timestamp);
            
            // 删除超过数量限制的条目
            while (autoSaves.length > this.AUTO_SAVE_CONFIG.MAX_ENTRIES) {
                const oldest = autoSaves.shift();
                localStorage.removeItem(oldest.key);
                console.log(`清理旧自动保存: ${oldest.key}`);
            }
            
            // 删除超过时间限制的条目
            const now = Date.now();
            autoSaves.forEach(item => {
                if (now - item.timestamp > this.AUTO_SAVE_CONFIG.MAX_AGE) {
                    localStorage.removeItem(item.key);
                    console.log(`清理过期自动保存: ${item.key}`);
                }
            });
        } catch (e) {
            console.error('清理旧自动保存失败:', e);
        }
    },

    /**
     * 自动保存当前文件
     */
    autoSaveCurrentFile() {
        const content = HPLEditor.getValue();
        const fileData = this.openFiles.get(this.currentFile);
        if (!fileData) return;
        
        // 检查内容大小
        if (!this._isValidAutoSaveSize(content)) {
            console.warn(`文件过大，跳过自动保存: ${this.currentFile}`);
            return;
        }
        
        try {
            // 先清理旧自动保存
            this._cleanupOldAutoSaves();
            
            const autoSaveKey = `hpl-autosave-${this.currentFile}`;
            localStorage.setItem(autoSaveKey, JSON.stringify({
                content: content,
                timestamp: Date.now(),
                file: this.currentFile
            }));
            
            console.log(`自动保存: ${this.currentFile}`);
            HPLUI.showAutoSaveIndicator();
        } catch (e) {
            if (e.name === 'QuotaExceededError') {
                console.error('localStorage 空间不足，清理旧自动保存后重试');
                this._cleanupOldAutoSaves();
                // 重试一次
                try {
                    const autoSaveKey = `hpl-autosave-${this.currentFile}`;
                    localStorage.setItem(autoSaveKey, JSON.stringify({
                        content: content,
                        timestamp: Date.now(),
                        file: this.currentFile
                    }));
                    console.log(`自动保存成功（重试）: ${this.currentFile}`);
                } catch (retryError) {
                    console.error('自动保存重试失败:', retryError);
                }
            } else {
                console.error('自动保存失败:', e);
            }
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
        
        // 追踪 blob URL
        this._blobUrls.add(url);
        
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
            // 延迟清理 blob URL，确保下载开始
            setTimeout(() => {
                URL.revokeObjectURL(url);
                this._blobUrls.delete(url);
            }, 1000);
        }
    },

    /**
     * 清理所有 blob URL 资源
     */
    cleanupBlobUrls() {
        this._blobUrls.forEach(url => {
            try {
                URL.revokeObjectURL(url);
            } catch (e) {
                console.warn('清理 blob URL 失败:', e);
            }
        });
        this._blobUrls.clear();
    },


    /**
     * 确认保存（从对话框）
     * 修复：正确处理已存在的文件，避免重复创建条目
     */
    confirmSave(filename) {
        if (!filename || !HPLUtils.isValidFilename(filename)) {
            HPLUI.showOutput('错误: 文件名无效', 'error');
            return;
        }
        
        // 确保文件名有扩展名
        const finalFilename = filename.endsWith('.hpl') ? filename : filename + '.hpl';
        
        // 修复：检查文件是否已打开，如果已打开则更新内容而不是创建新条目
        if (this.openFiles.has(finalFilename)) {
            // 文件已存在，更新内容
            const fileData = this.openFiles.get(finalFilename);
            fileData.content = HPLEditor.getValue();
            fileData.isModified = true;
            this.openFiles.set(finalFilename, fileData);
            
            // 更新标签页显示
            HPLUI.updateTabTitle(finalFilename, true);
            HPLUI.updateFileInfo(finalFilename, true);
            
            // 执行保存
            HPLUI.hideSaveDialog();
            this.saveCurrentFile();
        } else {
            // 新文件，创建新条目
            this.openFileInEditor(finalFilename, HPLEditor.getValue(), true);
            HPLUI.hideSaveDialog();
            this.saveCurrentFile();
        }
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
        
        // 添加到最近文件
        if (!isNew) {
            this.addToRecentFiles(filename);
        }
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
        
        // 清理相关资源
        this.cleanupBlobUrls();
        
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
     * 初始化拖放支持
     */
    initDragAndDrop() {

        const editorElement = document.getElementById('editor');
        const fileTree = document.getElementById('file-tree');
        const sidebar = document.getElementById('sidebar');
        
        // 编辑器拖放 - 打开文件
        if (editorElement) {
            editorElement.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                editorElement.classList.add('drag-over');
            });
            
            editorElement.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                editorElement.classList.remove('drag-over');
            });
            
            editorElement.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                editorElement.classList.remove('drag-over');
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    // 只处理第一个文件
                    const file = files[0];
                    if (this._isValidFileType(file.name)) {
                        this.openFromFileInput(file);
                        HPLUI.showOutput(`📂 已拖入文件: ${file.name}`, 'success');
                    } else {
                        HPLUI.showOutput(`❌ 不支持的文件类型: ${file.name}`, 'error');
                    }
                }
            });
        }
        
        // 文件树拖放 - 上传/移动文件
        if (fileTree) {
            fileTree.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                fileTree.classList.add('drag-over');
            });
            
            fileTree.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                fileTree.classList.remove('drag-over');
            });
            
            fileTree.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                fileTree.classList.remove('drag-over');
                
                const files = e.dataTransfer.files;
                Array.from(files).forEach(file => {
                    if (this._isValidFileType(file.name)) {
                        // 这里可以实现上传到服务器的逻辑
                        HPLUI.showOutput(`📤 准备上传: ${file.name}`, 'info');
                    }
                });
            });
        }
        
        // 防止默认拖放行为
        document.addEventListener('dragover', (e) => {
            if (e.target.closest('#editor') || e.target.closest('#file-tree')) {
                return;
            }
            e.preventDefault();
        });
        
        document.addEventListener('drop', (e) => {
            if (e.target.closest('#editor') || e.target.closest('#file-tree')) {
                return;
            }
            e.preventDefault();
        });
    },

    /**
     * 检查文件类型是否有效
     */
    _isValidFileType(filename) {
        const validExtensions = ['.hpl', '.txt', '.yaml', '.yml', '.json', '.py'];
        const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
        return validExtensions.includes(ext) || filename.endsWith('.hpl');
    },

    /**
     * 初始化文件右键菜单
     */
    initContextMenu() {
        const fileTree = document.getElementById('file-tree');
        if (!fileTree) return;
        
        // 创建右键菜单元素
        this._createContextMenuElement();
        
        // 绑定右键事件
        fileTree.addEventListener('contextmenu', (e) => {
            const fileItem = e.target.closest('.file-item');
            if (!fileItem) return;
            
            e.preventDefault();
            this._showContextMenu(e, fileItem);
        });
        
        // 点击其他地方关闭菜单
        document.addEventListener('click', () => {
            this._hideContextMenu();
        });
    },

    /**
     * 创建右键菜单元素
     */
    _createContextMenuElement() {
        // 移除已存在的菜单
        const existingMenu = document.getElementById('file-context-menu');
        if (existingMenu) {
            existingMenu.remove();
        }
        
        const menu = document.createElement('div');
        menu.id = 'file-context-menu';
        menu.className = 'context-menu hidden';
        menu.innerHTML = `
            <div class="context-menu-item" data-action="rename">
                <span class="context-menu-icon">✏️</span>
                <span>重命名</span>
            </div>
            <div class="context-menu-item" data-action="copy">
                <span class="context-menu-icon">📋</span>
                <span>复制</span>
            </div>
            <div class="context-menu-item" data-action="delete">
                <span class="context-menu-icon">🗑️</span>
                <span>删除</span>
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" data-action="refresh">
                <span class="context-menu-icon">🔄</span>
                <span>刷新</span>
            </div>
        `;
        
        document.body.appendChild(menu);
        
        // 绑定菜单项点击事件
        menu.addEventListener('click', (e) => {
            const item = e.target.closest('.context-menu-item');
            if (!item) return;
            
            const action = item.dataset.action;
            const targetFile = menu.dataset.targetFile;
            
            switch(action) {
                case 'rename':
                    this._startRenameFile(targetFile);
                    break;
                case 'copy':
                    this._copyFile(targetFile);
                    break;
                case 'delete':
                    this._deleteFile(targetFile);
                    break;
                case 'refresh':
                    if (typeof HPLApp !== 'undefined') {
                        HPLApp.refreshFileTree();
                    }
                    break;
            }
            
            this._hideContextMenu();
        });
    },

    /**
     * 显示右键菜单
     */
    _showContextMenu(e, fileItem) {
        const menu = document.getElementById('file-context-menu');
        if (!menu) return;
        
        const filename = fileItem.querySelector('.file-name')?.textContent;
        if (!filename) return;
        
        menu.dataset.targetFile = filename;
        
        // 定位菜单
        const x = e.pageX;
        const y = e.pageY;
        
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
        menu.classList.remove('hidden');
        
        // 确保菜单不超出视口
        const rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            menu.style.left = `${x - rect.width}px`;
        }
        if (rect.bottom > window.innerHeight) {
            menu.style.top = `${y - rect.height}px`;
        }
    },

    /**
     * 隐藏右键菜单
     */
    _hideContextMenu() {
        const menu = document.getElementById('file-context-menu');
        if (menu) {
            menu.classList.add('hidden');
        }
    },

    /**
     * 开始重命名文件
     */
    _startRenameFile(oldFilename) {
        const newFilename = prompt('请输入新文件名:', oldFilename);
        if (!newFilename || newFilename === oldFilename) return;
        
        if (!HPLUtils.isValidFilename(newFilename)) {
            HPLUI.showOutput('❌ 文件名无效', 'error');
            return;
        }
        
        // 如果文件已打开，更新标签页
        if (this.openFiles.has(oldFilename)) {
            const fileData = this.openFiles.get(oldFilename);
            this.openFiles.delete(oldFilename);
            this.openFiles.set(newFilename, fileData);
            
            if (this.currentFile === oldFilename) {
                this.currentFile = newFilename;
            }
            
            // 更新标签页
            HPLUI.removeTab(oldFilename);
            this.createTab(newFilename, fileData.isModified ? newFilename + '*' : newFilename);
            HPLUI.switchTab(newFilename);
        }
        
        HPLUI.showOutput(`✅ 已重命名: ${oldFilename} → ${newFilename}`, 'success');
    },

    /**
     * 复制文件
     */
    _copyFile(filename) {
        const newFilename = this._generateCopyFilename(filename);
        
        if (this.openFiles.has(filename)) {
            const fileData = this.openFiles.get(filename);
            this.openFileInEditor(newFilename, fileData.content, true);
        }
        
        HPLUI.showOutput(`📋 已复制: ${filename} → ${newFilename}`, 'success');
    },

    /**
     * 生成复制文件名
     */
    _generateCopyFilename(filename) {
        const dotIndex = filename.lastIndexOf('.');
        const name = dotIndex > 0 ? filename.slice(0, dotIndex) : filename;
        const ext = dotIndex > 0 ? filename.slice(dotIndex) : '';
        
        let copyName = `${name}_copy${ext}`;
        let counter = 1;
        
        while (this.openFiles.has(copyName)) {
            copyName = `${name}_copy${counter}${ext}`;
            counter++;
        }
        
        return copyName;
    },

    /**
     * 删除文件
     */
    _deleteFile(filename) {
        if (!confirm(`确定要删除文件 "${filename}" 吗？`)) {
            return;
        }
        
        // 如果文件已打开，先关闭
        if (this.openFiles.has(filename)) {
            this.closeFile(filename);
        }
        
        HPLUI.showOutput(`🗑️ 已删除: ${filename}`, 'success');
    },

    /**
     * 获取文件图标
     */
    getFileIcon(filename, isFolder = false, isExpanded = false) {
        if (isFolder) {
            return isExpanded ? '📂' : '📁';
        }
        
        const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
        
        const iconMap = {
            '.hpl': '📄',
            '.py': '🐍',
            '.js': '📜',
            '.html': '🌐',
            '.css': '🎨',
            '.json': '📋',
            '.yaml': '📋',
            '.yml': '📋',
            '.txt': '📝',
            '.md': '📖',
            '.xml': '📰',
            '.sql': '🗄️',
            '.sh': '⌨️',
            '.bat': '⌨️',
            '.log': '📜',
            '.ini': '⚙️',
            '.conf': '⚙️',
            '.config': '⚙️'
        };
        
        return iconMap[ext] || '📄';
    },

    /**
     * 更新文件树图标
     */
    updateFileTreeIcons() {
        const fileTree = document.getElementById('file-tree');
        if (!fileTree) return;
        
        fileTree.querySelectorAll('.file-item').forEach(item => {
            const fileNameEl = item.querySelector('.file-name');
            const iconEl = item.querySelector('.file-icon');
            
            if (fileNameEl && iconEl) {
                const filename = fileNameEl.textContent;
                const isFolder = item.classList.contains('folder');
                const isExpanded = item.classList.contains('expanded');
                
                iconEl.textContent = this.getFileIcon(filename, isFolder, isExpanded);
            }
        });
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLFileManager;
}
