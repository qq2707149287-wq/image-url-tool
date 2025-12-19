/**
 * sessions.js - 设备管理模块
 * 负责：查看活跃会话、强制下线设备
 * 从 auth.js 拆分而来 (原第1121-1231行)
 */

document.addEventListener("DOMContentLoaded", function () {
    // ==================== DOM 元素 ====================
    var viewSessionsBtn = document.getElementById("viewSessionsBtn");
    var sessionsModal = document.getElementById("sessionsModal");
    var sessionsTableBody = document.getElementById("sessionsTableBody");
    var sessionsModalCloseBtn = document.getElementById("sessionsModalCloseBtn");

    // ==================== 工具函数 ====================
    // ==================== 工具函数 ====================
    // 🔧 已统一移动到 core.js

    /**
     * 解析 User-Agent 获取设备名称
     */
    function parseDeviceName(ua) {
        if (!ua) return "🌐 未知设备";
        if (ua.includes("Windows")) return "🖥️ Windows PC";
        if (ua.includes("Mac")) return "💻 Mac";
        if (ua.includes("Android")) return "📱 Android";
        if (ua.includes("iPhone")) return "📱 iPhone";
        if (ua.includes("Linux")) return "🐧 Linux";
        return "🌐 浏览器";
    }

    // ==================== 事件绑定 ====================
    // 打开设备管理模态框
    if (viewSessionsBtn) {
        viewSessionsBtn.onclick = async function () {
            var token = getToken();
            if (!token) return;

            if (sessionsModal) sessionsModal.style.display = "flex";
            if (sessionsTableBody) {
                sessionsTableBody.innerHTML = "<tr><td colspan='4' style='padding:10px;text-align:center'>加载中...</td></tr>";
            }

            // 获取当前会话 ID
            var payload = parseJwt(token);
            var currentSid = payload.sid;

            try {
                var res = await fetch("/auth/sessions", {
                    headers: { "Authorization": "Bearer " + token }
                });
                var sessions = await res.json();

                if (sessionsTableBody) {
                    sessionsTableBody.innerHTML = "";

                    if (!sessions || sessions.length === 0) {
                        sessionsTableBody.innerHTML = "<tr><td colspan='4' style='padding:10px;text-align:center'>无活跃设备</td></tr>";
                    } else {
                        sessions.forEach(function (session) {
                            var tr = document.createElement("tr");
                            tr.style.borderBottom = "1px solid #eee";

                            var isCurrent = (session.session_id === currentSid);
                            var ua = session.device_info || "未知设备";
                            var deviceName = parseDeviceName(ua);

                            if (isCurrent) deviceName += " (当前设备)";

                            // 格式化时间
                            var lastActive = session.last_active;
                            try {
                                var date = new Date(session.last_active + "Z");
                                if (!isNaN(date)) lastActive = date.toLocaleString();
                            } catch (e) { }

                            // 操作按钮
                            var actionHtml = "";
                            if (isCurrent) {
                                actionHtml = "<span style='color:green;font-size:12px;'>在线</span>";
                            } else {
                                actionHtml = '<button class="btn-mini btn-danger" onclick="window.revokeSession(\'' + session.session_id + '\')">下线</button>';
                            }

                            tr.innerHTML =
                                '<td style="padding: 8px;">' +
                                '<div style="font-weight:bold">' + deviceName + '</div>' +
                                '<div style="font-size:11px;color:#999;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + ua + '">' + ua + '</div>' +
                                '</td>' +
                                '<td style="padding: 8px;">' + session.ip_address + '</td>' +
                                '<td style="padding: 8px;">' + lastActive + '</td>' +
                                '<td style="padding: 8px; text-align: right;">' + actionHtml + '</td>';

                            sessionsTableBody.appendChild(tr);
                        });
                    }
                }
            } catch (e) {
                console.error(e);
                if (sessionsTableBody) {
                    sessionsTableBody.innerHTML = "<tr><td colspan='4' style='padding:10px;text-align:center;color:red'>加载失败</td></tr>";
                }
            }
        };
    }

    // 关闭模态框
    if (sessionsModalCloseBtn) {
        sessionsModalCloseBtn.onclick = function () {
            if (sessionsModal) sessionsModal.style.display = "none";
        };
    }

    // 点击背景关闭
    if (sessionsModal) {
        sessionsModal.onclick = function (e) {
            if (e.target === sessionsModal) {
                sessionsModal.style.display = "none";
            }
        };
    }

    // ==================== 全局函数 ====================
    /**
     * 强制下线指定会话
     */
    window.revokeSession = async function (sid) {
        if (!confirm("确定要强制该设备下线吗？")) return;

        try {
            var res = await fetch("/auth/sessions/" + sid, {
                method: "DELETE",
                headers: { "Authorization": "Bearer " + getToken() }
            });
            if (res.ok) {
                if (window.showToast) window.showToast("已强制下线", "success");
                // 刷新列表
                if (viewSessionsBtn) viewSessionsBtn.click();
            } else {
                alert("操作失败");
            }
        } catch (e) {
            console.error(e);
            alert("网络错误");
        }
    };
});
