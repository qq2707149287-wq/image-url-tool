/**
 * account.js - 账号管理模块
 * 负责：VIP激活、修改用户名、修改密码、注销账号
 * 从 auth.js 拆分而来
 */

document.addEventListener("DOMContentLoaded", function () {
    // ==================== DOM 元素 ====================
    var changeUsernameBtn = document.getElementById("changeUsernameBtn");
    var changePasswordBtn = document.getElementById("changePasswordBtn");
    var deleteAccountLink = document.getElementById("deleteAccountLink");
    var activateVipBtn = document.getElementById("activateVipBtn");

    // ==================== 工具函数 ====================
    // 🔧 已统一移动到 core.js 和 ui.js


    // ==================== 修改用户名 ====================
    if (changeUsernameBtn) {
        changeUsernameBtn.onclick = function () {
            showInputModal(
                "修改用户名",
                "请输入新用户名:",
                [{ id: "new_username", placeholder: "新用户名" }],
                async function (values, close) {
                    var newUsername = values.new_username;
                    if (!newUsername || newUsername.length < 3) {
                        alert("用户名至少3个字符");
                        return;
                    }

                    try {
                        var res = await fetch("/auth/change-username", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer " + getToken()
                            },
                            body: JSON.stringify({ new_username: newUsername })
                        });
                        var data = await res.json();

                        if (res.ok) {
                            // 更新本地存储
                            localStorage.setItem("username", newUsername);
                            var currentUserDisplay = document.getElementById("currentUserDisplay");
                            if (currentUserDisplay) currentUserDisplay.innerText = newUsername;
                            if (window.showToast) window.showToast("用户名修改成功", "success");
                            close();
                        } else {
                            alert(data.detail || "修改失败");
                        }
                    } catch (e) {
                        console.error(e);
                        alert("网络错误");
                    }
                }
            );
        };
    }

    // ==================== 修改密码 ====================
    if (changePasswordBtn) {
        changePasswordBtn.onclick = function () {
            showInputModal(
                "修改密码",
                "请填写旧密码和新密码",
                [
                    { id: "old_pass", type: "password", placeholder: "旧密码" },
                    { id: "new_pass", type: "password", placeholder: "新密码 (至少6位)" },
                    { id: "confirm_pass", type: "password", placeholder: "确认新密码" }
                ],
                async function (values, close) {
                    var oldPass = values.old_pass;
                    var newPass = values.new_pass;
                    var confirmPass = values.confirm_pass;

                    if (!oldPass || !newPass || newPass.length < 6) {
                        alert("密码格式错误");
                        return;
                    }
                    if (newPass !== confirmPass) {
                        alert("两次新密码不一致");
                        return;
                    }

                    try {
                        var res = await fetch("/auth/change-password", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer " + getToken()
                            },
                            body: JSON.stringify({ old_password: oldPass, new_password: newPass })
                        });
                        var data = await res.json();

                        if (res.ok) {
                            if (window.showToast) window.showToast("密码修改成功", "success");
                            close();
                        } else {
                            alert(data.detail || "修改失败");
                        }
                    } catch (e) {
                        console.error(e);
                        alert("网络错误");
                    }
                }
            );
        };
    }

    // ==================== 注销账号 ====================
    if (deleteAccountLink) {
        deleteAccountLink.onclick = function () {
            showInputModal(
                "确认注销账号",
                '此操作不可恢复！请输入 "DELETE" 以确认注销:',
                [{ id: "confirm_text", placeholder: "DELETE" }],
                async function (values, close) {
                    if (values.confirm_text !== "DELETE") {
                        alert('请输入 "DELETE" 确认注销');
                        return;
                    }

                    try {
                        var res = await fetch("/auth/delete-account", {
                            method: "DELETE",
                            headers: { "Authorization": "Bearer " + getToken() }
                        });
                        var data = await res.json();

                        if (res.ok) {
                            if (window.showToast) window.showToast("账号已注销", "info");
                            if (typeof handleLogout === 'function') handleLogout();
                            close();
                        } else {
                            alert(data.detail || "注销失败");
                        }
                    } catch (e) {
                        console.error(e);
                        alert("网络错误");
                    }
                }
            );
        };
    }
    // ==================== 用户统计 ====================
    window.loadUserStats = async function () {
        var token = getToken();
        if (!token) return;
        var userEmailDisplay = document.getElementById("userEmailDisplay");
        var userStatsDisplay = document.getElementById("userStatsDisplay");

        try {
            var res = await fetch("/auth/user-stats", {
                headers: { "Authorization": "Bearer " + token }
            });
            if (res.ok) {
                var stats = await res.json();
                // 显示邮箱（部分隐藏）
                if (stats.email && userEmailDisplay) {
                    var email = stats.email;
                    var parts = email.split("@");
                    if (parts[0].length > 3) {
                        var masked = parts[0].substring(0, 2) + "****" + parts[0].slice(-1) + "@" + parts[1];
                        userEmailDisplay.innerText = "📧 " + masked;
                    } else {
                        userEmailDisplay.innerText = "📧 " + email;
                    }
                }
                // 显示统计
                if (userStatsDisplay) {
                    var info = "已上传 " + stats.upload_count + " 张图片";
                    var vipInfo = stats.is_vip ? ("VIP到期: " + (stats.vip_expiry ? stats.vip_expiry.split("T")[0] : "无限期")) : "普通用户";
                    var createdAt = stats.created_at ? stats.created_at.split("T")[0] : "未知";
                    userStatsDisplay.innerHTML = `注册: ${createdAt} | 上传: ${stats.upload_count || 0} | ${vipInfo}`;
                }
            }
        } catch (e) {
            console.error("加载统计失败", e);
        }
    };
});
