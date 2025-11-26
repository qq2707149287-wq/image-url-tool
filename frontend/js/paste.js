"use strict";

function initPaste() {
    // 全局粘贴监听 (更稳)
    document.addEventListener("paste", function(e) {
        // 1. 检查当前是否在“粘贴”标签页
        var pasteContent = document.getElementById("content-paste");
        if (!pasteContent || !pasteContent.classList.contains("active")) {
            return; // 如果当前不在粘贴页，忽略
        }

        // 2. 如果焦点在输入框里（比如在填搜索框），不要拦截粘贴
        if (document.activeElement && 
           (document.activeElement.tagName === "INPUT" || 
            document.activeElement.tagName === "TEXTAREA")) {
            return;
        }

        handlePasteEvent(e);
    });

    // 点击粘贴区域给个视觉反馈
    var pasteArea = document.getElementById("pasteArea");
    if (pasteArea) {
        pasteArea.onclick = function() {
            this.style.borderColor = "var(--primary)";
            setTimeout(() => {
                this.style.borderColor = "var(--success)";
            }, 200);
        };
    }

    // 绑定按钮
    if (typeof bindResultButtons === 'function') {
        bindResultButtons("paste");
    }
}

function handlePasteEvent(e) {
    var items = e.clipboardData.items;
    
    // 优先查找文件 (截图通常在这里)
    for (var i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") !== -1) {
            e.preventDefault(); // 阻止默认行为
            var file = items[i].getAsFile();
            if (file) {
                // 调用 upload.js 的上传函数
                if (typeof uploadFile === 'function') {
                    uploadFile(file, "paste", "粘贴上传");
                }
            }
            return; // 找到文件就停止，不再看 HTML/Text
        }
    }

    // 其次查找 HTML (右键复制图片)
    if (e.clipboardData.types.indexOf("text/html") !== -1) {
        e.preventDefault();
        var html = e.clipboardData.getData("text/html");
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, "text/html");
        var img = doc.querySelector("img");
        if (img && img.src) {
            if (typeof handleWebImage === 'function') handleWebImage(img.src, "paste");
            return;
        }
    }

    // 最后查找纯文本 URL
    if (e.clipboardData.types.indexOf("text/plain") !== -1) {
        // 这里不阻止默认行为，因为如果用户只是想把文字贴到别处呢？
        // 但如果没有输入框焦点，我们可以尝试解析
        var text = e.clipboardData.getData("text/plain");
        if (text && text.trim().match(/^https?:\/\/.+/)) {
            e.preventDefault();
            if (typeof handleWebImage === 'function') handleWebImage(text.trim(), "paste");
            return;
        }
    }
}
