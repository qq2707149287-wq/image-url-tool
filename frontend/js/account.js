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
    /**
     * 获取当前 token
     */
    function getToken() {
        return localStorage.getItem("token");
    }

    /**
     * 通用输入弹窗 (如果 auth.js 没有暴露，这里自己实现一个简化版)
     */
    function showInputModal(title, message, inputs, callback) {
        // 尝试使用 auth.js 暴露的全局函数
        if (typeof window.showInputModal === 'function') {
            window.showInputModal(title, message, inputs, callback);
            return;
        }

        // 简化版实现
        var values = {};
        inputs.forEach(function (input) {
            var value = prompt(message + "\n" + input.placeholder);
            values[input.id] = value;
        });
        if (callback) callback(values, function () { });
    }

    // ==================== VIP 激活 ====================
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
                            if (typeof checkLoginStatus === 'function') checkLoginStatus();
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
});
