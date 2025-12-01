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

window.showToast = function(message, type) {
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
    
    setTimeout(function() {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(function() { 
            if (container.contains(toast)) container.removeChild(toast); 
        }, 300);
    }, 3000);
};
