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
};

