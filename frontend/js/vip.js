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
    // 🔧 已统一移动到 core.js 和 ui.js


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
                        // 🐱 DEBUG: 打印发送的数据喵！
                        var postData = { days: days, count: count };
                        alert("[DEBUG vip.js]\ndays=" + days + " (type: " + typeof days + ")\ncount=" + count + " (type: " + typeof count + ")\n\nJSON: " + JSON.stringify(postData));

                        var res = await fetch("/admin/vip/generate", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer " + getToken()
                            },
                            body: JSON.stringify(postData)
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
                            alert("生成失败: " + JSON.stringify(data.detail || data));
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

    // ==================== 商业化：定价与购买 ====================
    var upgradeVipBtn = document.getElementById("upgradeVipBtn");
    var pricingModal = document.getElementById("pricingModal");
    var buyVipBtn = document.getElementById("buyVipBtn");

    // 淘宝店铺链接 (可以在 config.js 或这里配置)
    // 暂时用 generic link, 待用户提供后替换
    var SHOP_URL = "https://shop.taobao.com/";

    if (upgradeVipBtn && pricingModal) {
        upgradeVipBtn.onclick = function () {
            pricingModal.style.display = "flex";
        };
    }

    if (buyVipBtn) {
        buyVipBtn.onclick = function () {
            // 在新标签页打开购买链接
            window.open(SHOP_URL, "_blank");
            // 可选：关闭定价弹窗，打开激活弹窗，引导闭环
            // pricingModal.style.display = "none";
            // if (activateVipBtn) activateVipBtn.click();
        };
    }
});
