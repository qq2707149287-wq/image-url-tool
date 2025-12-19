/**
 * vip.js - VIP 与 管理员功能模块
 * 负责：用户激活 VIP、管理员生成 VIP 码、管理员审计模式
 * 从 auth.js 和 account.js 拆分而来
 */

document.addEventListener("DOMContentLoaded", function () {
    // ==================== DOM 元素 ====================
    var activateVipBtn = document.getElementById("activateVipBtn");
    var generateVipCodesBtn = document.getElementById("generateVipCodesBtn");
    var adminAuditBtn = document.getElementById("adminAuditBtn");

    // ==================== 工具函数 ====================
    function getToken() {
        return localStorage.getItem("token");
    }

    /**
     * 通用输入弹窗 (尝试使用全局定义的，如果没有则降级)
     */
    function showInputModal(title, message, inputs, callback) {
        if (typeof window.showInputModal === 'function') {
            window.showInputModal(title, message, inputs, callback);
        } else {
            // 降级实现
            var values = {};
            inputs.forEach(function (input) {
                var value = prompt(message + "\n" + (input.label || input.placeholder));
                values[input.id] = value;
            });
            if (callback) callback(values, function () { });
        }
    }

    // ==================== VIP 激活 (用户功能) ====================
    if (activateVipBtn) {
        activateVipBtn.onclick = function () {
            showInputModal(
                "💎 激活 VIP",
                "请输入您的 VIP 激活码:",
                [{ id: "vip_code", placeholder: "XXXX-XXXX-XXXX-XXXX" }],
                async function (values, close) {
                    var code = values.vip_code;
                    if (!code || code.trim() === "") {
                        alert("请输入激活码");
                        return;
                    }

                    try {
                        var res = await fetch("/auth/vip/activate", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer " + getToken()
                            },
                            body: JSON.stringify({ code: code.trim() })
                        });
                        var data = await res.json();

                        if (res.ok) {
                            if (window.showToast) window.showToast("VIP 激活成功！有效期至: " + data.expiry, "success");
                            // 刷新登录状态以更新 UI (Badge 等)
                            if (typeof checkLoginStatus === 'function') {
                                checkLoginStatus();
                            } else if (window.checkLoginStatus) {
                                window.checkLoginStatus();
                            }
                            close();
                        } else {
                            alert(data.detail || "激活失败");
                        }
                    } catch (e) {
                        console.error(e);
                        alert("网络错误");
                    }
                }
            );
        };
    }

    // ==================== 批量生成激活码 (管理员功能) ====================
    if (generateVipCodesBtn) {
        generateVipCodesBtn.onclick = function () {
            showInputModal(
                "📥 批量生成激活码",
                "请输入生成数量和天数:",
                [
                    { id: "vip_days", label: "有效期(天)", value: "30", type: "number" },
                    { id: "vip_count", label: "生成数量(个)", value: "10", type: "number" }
                ],
                async function (values, close) {
                    var days = parseInt(values.vip_days);
                    var count = parseInt(values.vip_count);

                    if (!days || days <= 0 || !count || count <= 0) {
                        alert("请输入有效的数字");
                        return;
                    }

                    try {
                        var formData = new FormData();
                        formData.append("days", days);
                        formData.append("count", count);

                        var res = await fetch("/admin/vip/generate", {
                            method: "POST",
                            headers: {
                                "Authorization": "Bearer " + getToken()
                            },
                            body: formData
                        });
                        var data = await res.json();

                        if (res.ok && data.success) {
                            var codes = data.codes;
                            if (codes && codes.length > 0) {
                                // 自动下载
                                var codeList = codes.join("\n");
                                var blob = new Blob([codeList], { type: "text/plain;charset=utf-8" });
                                var url = URL.createObjectURL(blob);
                                var a = document.createElement("a");
                                a.href = url;
                                a.download = "vip_codes_" + Date.now() + ".txt";
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                URL.revokeObjectURL(url);

                                if (window.showToast) window.showToast("成功生成 " + codes.length + " 个激活码并已自动下载", "success");
                            }
                            close();
                        } else {
                            alert(data.detail || "生成失败");
                        }
                    } catch (e) {
                        console.error(e);
                        alert("网络错误");
                    }
                }
            );
        };
    }

    // ==================== 上帝视角审计 (管理员功能) ====================
    if (adminAuditBtn) {
        adminAuditBtn.onclick = function () {
            // 1. 关闭可能打开的设置模态框
            var settingsModal = document.getElementById("settingsModal");
            if (settingsModal) settingsModal.style.display = "none";

            // 2. 切换到历史记录 Tab
            var tabHistory = document.getElementById("tab-history");
            if (tabHistory) tabHistory.click();

            // 3. 触发 history.js 的审计模式
            // history.js 应该暴露一个方法或者检查全局变量
            if (typeof window.forceAdminAuditMode === 'function') {
                window.forceAdminAuditMode();
            } else {
                console.warn("history.js 未加载或未暴露 forceAdminAuditMode");
                if (window.showToast) window.showToast("审计功能未就绪，请稍后重试", "warning");
            }
        };
    }
});
