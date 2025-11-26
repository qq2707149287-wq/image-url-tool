"use strict";

function initUI() {
    // Tab 切换
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () { switchTab(this.id); };
    }

    // 深色模式
    var themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        var savedTheme = localStorage.getItem("theme");
        if (savedTheme === "dark") {
            document.body.setAttribute("data-theme", "dark");
            themeToggle.textContent = "☀️ 亮色模式";
        }
        themeToggle.onclick = function () {
            var current = document.body.getAttribute("data-theme");
            if (current === "dark") {
                document.body.removeAttribute("data-theme");
                this.textContent = "🌙 深色模式";
                localStorage.setItem("theme", "light");
            } else {
                document.body.setAttribute("data-theme", "dark");
                this.textContent = "☀️ 亮色模式";
                localStorage.setItem("theme", "dark");
            }
        };
    }

    // 初始化图床排序 (新增)
    initDraggableServices();
}

// [新增] 图床拖拽排序功能
function initDraggableServices() {
    var groups = document.querySelectorAll(".checkbox-group");
    
    groups.forEach(function(group) {
        var labels = group.querySelectorAll("label");
        
        labels.forEach(function(label) {
            label.setAttribute("draggable", "true");
            
            // 拖拽开始
            label.addEventListener("dragstart", function(e) {
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", null); // 兼容 Firefox
                label.classList.add("dragging");
                window.draggedLabel = label; // 记录当前拖拽元素
            });

            // 拖拽结束
            label.addEventListener("dragend", function(e) {
                label.classList.remove("dragging");
                window.draggedLabel = null;
                
                // 拖拽结束后，保存新的顺序到 LocalStorage (复用 upload.js 里的逻辑)
                // 稍后 upload.js 上传时会按 DOM 顺序读取，所以这就实现了优先级
                if (typeof window.saveServiceSelectionFromUI === 'function') {
                    window.saveServiceSelectionFromUI(group);
                }
            });

            // 拖拽经过
            label.addEventListener("dragover", function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                
                var target = e.target.closest("label");
                if (target && target !== window.draggedLabel && group.contains(target)) {
                    // 判断是在前还是在后
                    var rect = target.getBoundingClientRect();
                    var next = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
                    
                    if (next) {
                        group.insertBefore(window.draggedLabel, target.nextSibling);
                    } else {
                        group.insertBefore(window.draggedLabel, target);
                    }
                }
            });
        });
    });
}

function switchTab(tabId) {
    // ... (保持原有的 switchTab 逻辑不变)
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove("active");
    var contents = document.querySelectorAll(".tab-content");
    for (var j = 0; j < contents.length; j++) contents[j].classList.remove("active");
    var currentTab = document.getElementById(tabId);
    if (currentTab) currentTab.classList.add("active");
    var contentId = tabId.replace("tab-", "content-");
    var content = document.getElementById(contentId);
    if (content) {
        content.classList.add("active");
        if (contentId === "content-history" && typeof displayHistory === 'function') displayHistory();
        if (contentId === "content-paste") {
             var pasteArea = document.getElementById("pasteArea");
             if(pasteArea) pasteArea.focus();
        }
    }
}

window.showToast = function(message, type) {
    var container = document.getElementById("toast-container");
    if (!container) return;
    var toast = document.createElement("div");
    toast.className = "toast " + (type || "success");
    var icon = type === "error" ? "❌" : (type === "warning" ? "⚠️" : "✅");
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(function() {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(function() { if(container.contains(toast)) container.removeChild(toast); }, 300);
    }, 3000);
};

window.showError = function(msg, tab) {
    var prefix = tab === "paste" ? "paste" : "upload";
    var errorBox = document.getElementById(prefix + "Error");
    var errorMsg = document.getElementById(prefix + "ErrorMessage");
    var loading = document.getElementById(prefix + "Loading");
    if (loading) loading.style.display = "none";
    if (errorBox && errorMsg) {
        errorMsg.textContent = msg;
        errorBox.style.display = "block";
    } else {
        window.showToast(msg, "error");
    }
};
