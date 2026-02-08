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
    }
};

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HPLFileManager;
}
