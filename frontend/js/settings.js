/**
 * settings.js - 系统设置模块
 * 负责：调试模式开关、系统设置加载/保存
 * 从 auth.js 拆分而来 (原第971-1050行)
 */

document.addEventListener("DOMContentLoaded", function () {
    // ==================== DOM 元素 ====================
    var settingsBtn = document.getElementById("settingsBtn");
    var settingsModal = document.getElementById("settingsModal");
    var settingsModalCloseBtn = document.getElementById("settingsModalCloseBtn");
    var debugModeToggle = document.getElementById("debugModeToggle");

    // ==================== 状态变量 ====================
    // 调试模式状态 (全局共享)
    window.isDebugMode = false;

    // ==================== 初始化 ====================
    loadSystemSettings();

    // ==================== 事件绑定 ====================
    // 打开设置模态框
    if (settingsBtn) {
        settingsBtn.onclick = function () {
            if (settingsModal) settingsModal.style.display = "flex";
        };
    }

    // 关闭设置模态框
    if (settingsModalCloseBtn) {
        settingsModalCloseBtn.onclick = function () {
            if (settingsModal) settingsModal.style.display = "none";
        };
    }

    // 点击背景关闭
    if (settingsModal) {
        settingsModal.onclick = function (e) {
            if (e.target === settingsModal) {
                settingsModal.style.display = "none";
            }
        };
    }

    // 调试模式开关
    if (debugModeToggle) {
        debugModeToggle.onchange = async function () {
            var newValue = this.checked;
            // 🔧 立即更新 UI，不等后端返回，防止视觉延迟
            document.body.classList.toggle('debug-mode', newValue);

            try {
                var res = await fetch("/system/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ debug_mode: newValue })
                });
                if (res.ok) {
                    var data = await res.json();
                    window.isDebugMode = data.debug_mode;
                    // 再次确认状态 (防回滚)
                    document.body.classList.toggle('debug-mode', window.isDebugMode);
                    if (window.showToast) window.showToast("调试模式已" + (window.isDebugMode ? "开启" : "关闭"), "success");
                    // 刷新 UI (如果注册框已打开)
                    if (typeof updateModalUI === 'function') updateModalUI();
                }
            } catch (e) {
                console.error(e);
                this.checked = !newValue; // 回滚
                document.body.classList.toggle('debug-mode', !newValue);
                alert("设置保存失败");
            }
        };
    }

    // ==================== 函数定义 ====================
    /**
     * 加载系统设置
     */
    async function loadSystemSettings() {
        try {
            var res = await fetch("/system/settings");
            if (res.ok) {
                var settings = await res.json();
                window.isDebugMode = settings.debug_mode || false;
                if (debugModeToggle) debugModeToggle.checked = window.isDebugMode;
                // 🔧 CSS 大法：同步更新 body 的 class 喵~
                document.body.classList.toggle('debug-mode', window.isDebugMode);
                console.log("✅ 系统设置已加载: Debug Mode =", window.isDebugMode);
            }
        } catch (e) {
            console.error("❌ 加载系统设置失败:", e);
        }
    }

    // 暴露给全局，让其他模块可以调用
    window.loadSystemSettings = loadSystemSettings;
});
