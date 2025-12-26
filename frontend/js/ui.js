"use strict";

function initUI() {
    // Tab 切换
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () { switchTab(this.id); };
    }

    // 深色模式切换
    var themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        var sunSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>';
        var moonSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';

        function updateThemeIcon(isDark) {
            themeToggle.innerHTML = isDark ? sunSvg : moonSvg;
            themeToggle.setAttribute("title", isDark ? "切换亮色模式" : "切换深色模式");
        }

        var savedTheme = localStorage.getItem("theme");
        if (savedTheme === "dark") {
            document.body.setAttribute("data-theme", "dark");
            updateThemeIcon(true);
        } else {
            updateThemeIcon(false);
        }

        themeToggle.onclick = function () {
            var current = document.body.getAttribute("data-theme");
            if (current === "dark") {
                document.body.removeAttribute("data-theme");
                updateThemeIcon(false);
                localStorage.setItem("theme", "light");
            } else {
                document.body.setAttribute("data-theme", "dark");
                updateThemeIcon(true);
                localStorage.setItem("theme", "dark");
            }
        };
    }

    // === 拖拽悬浮自动切换标签页功能 ===
    var dragHoverTimer = null;
    var dragHoverTarget = null;

    for (var i = 0; i < tabs.length; i++) {
        (function (tab) {
            // 当拖拽文件悬浮在标签按钮上时
            tab.addEventListener('dragenter', function (e) {
                e.preventDefault();

                // 如果已经是当前标签，不需要切换
                if (tab.classList.contains('active')) return;

                // 清除之前的定时器
                if (dragHoverTimer) {
                    clearTimeout(dragHoverTimer);
                }

                dragHoverTarget = tab;

                // 设置定时器，悬浮600ms后自动切换
                dragHoverTimer = setTimeout(function () {
                    if (dragHoverTarget === tab) {
                        switchTab(tab.id);
                        // 显示提示
                        if (window.showToast) {
                            window.showToast("已切换到 " + tab.textContent, "success");
                        }
                    }
                }, 600);
            });

            tab.addEventListener('dragleave', function (e) {
                // 清除定时器
                if (dragHoverTarget === tab) {
                    if (dragHoverTimer) {
                        clearTimeout(dragHoverTimer);
                        dragHoverTimer = null;
                    }
                    dragHoverTarget = null;
                }
            });

            tab.addEventListener('dragover', function (e) {
                e.preventDefault(); // 允许drop
            });
        })(tabs[i]);
    }
}

function switchTab(tabId) {
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
        if (contentId === "content-history" && typeof displayHistory === 'function') {
            displayHistory();
        }
        if (contentId === "content-paste") {
            var pasteArea = document.getElementById("pasteArea");
            if (pasteArea) pasteArea.focus();
        }
    }
}

window.showToast = function (message, type) {
    var container = document.getElementById("toast-container");
    if (!container) return;

    var toast = document.createElement("div");
    toast.className = "toast " + (type || "success");

    var icon = "✅";
    if (type === "error") icon = "❌";
    else if (type === "warning") icon = "⚠️";

    var iconSpan = document.createElement("span");
    iconSpan.textContent = icon;

    var msgSpan = document.createElement("span");
    msgSpan.textContent = " " + message;

    toast.appendChild(iconSpan);
    toast.appendChild(msgSpan);
    container.appendChild(toast);

    setTimeout(function () {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(function () {
            if (container.contains(toast)) container.removeChild(toast);
        }, 300);
    }, 3000);
};

// ===================================
// Generic Input Modal (通用输入弹窗)
// ===================================
window.showInputModal = function (title, message, inputs, callback) {
    var modal = document.getElementById("inputModal");
    var titleEl = document.getElementById("inputModalTitle");
    var msgEl = document.getElementById("inputModalMessage");
    var container = document.getElementById("inputContainer");
    var submitBtn = document.getElementById("inputModalSubmitBtn");
    var cancelBtn = document.getElementById("inputModalCancelBtn");
    var closeBtn = document.getElementById("inputModalCloseBtn");

    if (!modal) return;

    titleEl.innerText = title;
    msgEl.innerText = message || "";
    container.innerHTML = "";

    // Build inputs
    inputs.forEach(function (cfg) {
        var div = document.createElement("div");
        div.style.marginBottom = "10px";
        if (cfg.label) {
            var label = document.createElement("label");
            label.innerText = cfg.label;
            label.style.display = "block";
            label.style.marginBottom = "5px";
            div.appendChild(label);
        }
        var input = document.createElement("input");
        input.type = cfg.type || "text";
        input.value = cfg.value || "";
        input.placeholder = cfg.placeholder || "";
        input.className = "form-control";
        input.style.width = "100%";
        input.id = cfg.id;
        div.appendChild(input);
        container.appendChild(div);
    });

    // Handlers
    var closeModal = function () {
        modal.style.display = "none";
        // clear handlers to prevent leaks
        submitBtn.onclick = null;
    };

    submitBtn.onclick = function () {
        var values = {};
        inputs.forEach(function (cfg) {
            var el = document.getElementById(cfg.id);
            values[cfg.id] = el ? el.value : "";
        });
        callback(values, closeModal);
    };

    cancelBtn.onclick = closeModal;
    closeBtn.onclick = closeModal;

    modal.style.display = "flex";
    modal.style.display = "flex";
};

// ===================================
// New UI Logic for Homepage Refactor
// ===================================

// 全局点击事件处理 (用于关闭下拉菜单)
document.addEventListener('click', function (e) {
    var container = document.getElementById('userMenuContainer');
    if (container && !container.contains(e.target)) {
        var menu = document.getElementById('userDropdown');
        var trigger = document.getElementById('userMenuTrigger');
        if (menu) menu.style.display = 'none';
        if (trigger) trigger.classList.remove('active');
    }
});

// 用户菜单切换
window.toggleUserMenu = function () {
    var menu = document.getElementById('userDropdown');
    var trigger = document.getElementById('userMenuTrigger');
    if (!menu || !trigger) return;

    if (menu.style.display === 'block') {
        menu.style.display = 'none';
        trigger.classList.remove('active');
    } else {
        menu.style.display = 'block';
        trigger.classList.add('active');
    }
};

// 上传模式切换 (Segmented Control)
window.toggleUploadMode = function (mode, event) {
    // [FIX] 阻止事件冒泡，防止触发上传区域的文件选择
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }

    if (mode === 'private') {
        var token = localStorage.getItem("token");
        if (!token) {
            if (window.showToast) window.showToast("登录后可使用私有模式 (Guest 默认公开)", "info");
            return;
        }
        window.uploadSharedMode = false;
    } else {
        window.uploadSharedMode = true;
    }

    // 更新持久化存储
    localStorage.setItem("uploadSharedMode", window.uploadSharedMode ? "true" : "false");

    // 更新 UI
    window.updateUploadUI();
};

// 更新上传 UI 状态 (供 auth.js 和 upload.js 调用)
window.updateUploadUI = function () {
    var isShared = (typeof window.uploadSharedMode !== 'undefined') ? window.uploadSharedMode : true;

    // 如果没有全局变量，尝试从 localStorage 读取初始化
    if (typeof window.uploadSharedMode === 'undefined') {
        isShared = localStorage.getItem("uploadSharedMode") !== "false";
        window.uploadSharedMode = isShared;
    }

    var mode = isShared ? 'public' : 'private';

    // Update Segment Buttons
    var btns = document.querySelectorAll(".segment-btn");
    btns.forEach(function (b) {
        if (b.getAttribute("data-mode") === mode) {
            b.classList.add("active");
        } else {
            b.classList.remove("active");
        }
    });

    // Sync hidden button (legacy compatibility)
    var hiddenBtn = document.getElementById('uploadModeBtn');
    if (hiddenBtn) {
        if (isShared) hiddenBtn.classList.add('active');
        else hiddenBtn.classList.remove('active');
    }
};

// === 隐形调试模式 ===
// 连续点击副标题 5 次开启/关闭调试模式
document.addEventListener("DOMContentLoaded", function () {
    // 稍微延迟以等待 upload.js 初始化 global var
    setTimeout(window.updateUploadUI, 100);

    // Init Debug UI visibility
    // 检查调试模式状态，设置隐形设置项的可见性
    var isDebug = localStorage.getItem("debug_mode") === "true";
    var debugGroup = document.getElementById('debugSettingsGroup');
    if (debugGroup) debugGroup.style.display = isDebug ? 'block' : 'none';

    var subtitle = document.querySelector('.subtitle');
    var debugClicks = 0;
    var debugTimer = null;

    if (subtitle) {
        subtitle.addEventListener('click', function () {
            debugClicks++;
            if (debugTimer) clearTimeout(debugTimer);
            debugTimer = setTimeout(function () { debugClicks = 0; }, 1000); // 1秒内连击有效

            if (debugClicks >= 5) {
                toggleDebugMode();
                debugClicks = 0;
            }
        });
        // 鼠标变手型提示可点击
        subtitle.style.cursor = 'text';
    }
});

function toggleDebugMode() {
    var isDebug = localStorage.getItem("debug_mode") === "true";
    var newState = !isDebug;
    localStorage.setItem("debug_mode", newState);

    // 简单反馈
    if (window.showToast) {
        window.showToast("调试模式已" + (newState ? "开启 🛠️" : "关闭 🚫"), newState ? "success" : "info");
    }

    // Toggle hidden settings
    var debugGroup = document.getElementById('debugSettingsGroup');
    if (debugGroup) debugGroup.style.display = newState ? 'block' : 'none';

    // 如果有其他调试 UI，也可以在这里控制
    document.body.classList.toggle('debug-mode', newState);
}


