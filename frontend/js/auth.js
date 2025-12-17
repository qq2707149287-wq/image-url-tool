// [Fix] Google Sign-In 回调函数 (必须定义在全局作用域)
// 在 redirect 模式下，这个函数通常不会被调用（Google 直接 POST 到后端）
// 但 Google SDK 仍然需要它存在，否则会报错
function handleGoogleCredentialResponse(response) {
    // 这个函数在 redirect 模式下不会被调用
    // 如果意外被调用，尝试手动 POST 到后端
    console.log("[Google Login] Callback invoked (unexpected in redirect mode)");
    if (response && response.credential) {
        // 创建一个隐藏表单并提交到后端
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = '/auth/google-callback';

        var credInput = document.createElement('input');
        credInput.type = 'hidden';
        credInput.name = 'credential';
        credInput.value = response.credential;
        form.appendChild(credInput);

        document.body.appendChild(form);
        form.submit();
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // DOM Elements
    var authBtn = document.getElementById("authBtn");
    var authModal = document.getElementById("authModal");
    var authTitle = document.getElementById("authTitle");
    var authUsernameInput = document.getElementById("authUsername");
    var authPasswordInput = document.getElementById("authPassword");
    var authSubmitBtn = document.getElementById("authSubmitBtn");
    var authToggleLink = document.getElementById("authToggleLink");
    var authToggleText = document.getElementById("authToggleText");
    var authMessage = document.getElementById("authMessage");
    var authForm = document.getElementById("authFormContainer");
    var authUserInfo = document.getElementById("authUserInfoContainer");
    var currentUserDisplay = document.getElementById("currentUserDisplay");
    var logoutBtn = document.getElementById("logoutBtn");

    // New Elements
    var authEmailInput = document.getElementById("authEmail");
    var authCodeInput = document.getElementById("authCode");
    var sendCodeBtn = document.getElementById("sendCodeBtn");
    var emailGroup = document.getElementById("emailGroup");
    var codeGroup = document.getElementById("codeGroup");
    var forgotPasswordLink = document.getElementById("forgotPasswordLink");
    var passwordHint = document.getElementById("passwordHint");
    var rememberMeGroup = document.getElementById("rememberMeGroup");
    var authRememberMe = document.getElementById("authRememberMe");

    // Captcha Elements (验证码)
    var captchaGroup = document.getElementById("captchaGroup");
    var captchaImage = document.getElementById("captchaImage");
    var captchaInput = document.getElementById("captchaInput");
    var refreshCaptchaBtn = document.getElementById("refreshCaptchaBtn");
    var currentCaptchaId = null;  // 当前验证码ID

    // Modes: 'login', 'register', 'reset'
    var currentAuthMode = 'login';
    var token = localStorage.getItem("token");
    var username = localStorage.getItem("username");

    // Init State
    checkLoginStatus();

    // Event Listeners
    if (authBtn) {
        authBtn.onclick = function () {
            // Update modal state before showing
            if (token) {
                showUserInfo();
            } else {
                showLoginForm();
                resetForm();
            }
            authModal.style.display = "flex";
        };
    }

    if (authToggleLink) {
        authToggleLink.onclick = function () {
            if (currentAuthMode === 'login') {
                currentAuthMode = 'register';
            } else {
                currentAuthMode = 'login';
            }
            updateModalUI();
        };
    }

    if (forgotPasswordLink) {
        forgotPasswordLink.onclick = function () {
            currentAuthMode = 'reset';
            updateModalUI();
        }
    }

    if (sendCodeBtn) {
        sendCodeBtn.onclick = handleSendCode;
    }

    if (authSubmitBtn) {
        authSubmitBtn.onclick = handleAuthSubmit;
    }

    // [Fix] 添加 Enter 键支持，按回车可以直接提交喵~
    var authPasswordInput = document.getElementById("authPassword");
    if (authPasswordInput) {
        authPasswordInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                handleAuthSubmit();
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.onclick = handleLogout;
    }

    // Captcha Event Handlers (验证码事件)
    if (refreshCaptchaBtn) {
        refreshCaptchaBtn.onclick = loadCaptcha;
    }
    if (captchaImage) {
        captchaImage.onclick = loadCaptcha;  // 点击图片也可刷新
    }

    // 加载验证码
    async function loadCaptcha() {
        try {
            var res = await fetch('/captcha/generate');
            if (res.ok) {
                var data = await res.json();
                currentCaptchaId = data.captcha_id;
                if (captchaImage) captchaImage.src = data.image;
                if (captchaInput) captchaInput.value = '';
            }
        } catch (e) {
            console.error('加载验证码失败:', e);
        }
    }

    // Functions

    async function checkLoginStatus() {
        if (token && username) {
            // 先显示缓存的用户名
            if (authBtn) authBtn.innerText = "👤 " + username;

            // 验证 Token 并获取最新信息(如管理员状态)
            try {
                var res = await fetch("/auth/me", {
                    headers: { "Authorization": "Bearer " + token }
                });
                if (res.ok) {
                    var user = await res.json();

                    // [FIX] 同步最新的 VIP/Admin 状态到 localStorage (修复已登录用户状态不同步问题)
                    localStorage.setItem("is_vip", user.is_vip === true ? 'true' : 'false');
                    localStorage.setItem("is_admin", user.is_admin === true ? 'true' : 'false');

                    var badge = "";
                    if (user.is_admin) {
                        badge += " <span style='background:red;color:white;padding:2px 4px;border-radius:4px;font-size:0.8em'>ADMIN</span>";
                    }
                    if (user.is_vip) {
                        badge += " <span style='background:linear-gradient(45deg, #FFD700, #FFA500);color:white;padding:2px 4px;border-radius:4px;font-size:0.8em;margin-left:5px'>VIP</span>";
                    }
                    // 如果有头像，显示头像；否则显示默认图标
                    // 添加 onerror 处理，加载失败时回退到默认图标
                    var avatarHtml = user.avatar
                        ? "<img src='" + user.avatar + "' onerror=\"this.outerHTML='👤 '\" style='width:20px;height:20px;border-radius:50%;vertical-align:middle;margin-right:5px'>"
                        : "👤 ";
                    if (authBtn) {
                        // [Fix] 用户名过长截断处理
                        var nameHtml = "<span style='max-width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:inline-block; vertical-align:middle;'>" + user.username + "</span>";
                        authBtn.innerHTML = avatarHtml + nameHtml + badge;
                        authBtn.title = user.username; // 鼠标悬停显示全名
                    }
                    console.log("User avatar URL:", user.avatar); // Debug log

                    // 保存 admin 状态供其他模块使用 (如 history.js)
                    // 保存 admin 状态供其他模块使用 (如 history.js)
                    window.currentUser = user;

                    // 显示/隐藏管理员工具
                    var adminTools = document.getElementById("adminTools");
                    if (adminTools) {
                        adminTools.style.display = user.is_admin ? "block" : "none";
                    }

                    // 更新上传UI (因为 updateUploadUI 可能依赖 window.currentUser)
                    if (window.updateUploadUI) window.updateUploadUI();

                    // [NEW] 启动通知轮询
                    startNotificationPolling();
                } else {
                    // Token 过期或无效
                    handleLogout();
                }
            } catch (e) {
                console.error("Auth check failed", e);
            }
        } else {
            if (authBtn) authBtn.innerText = "👤 登录/注册";
            window.currentUser = null;
            var adminTools = document.getElementById("adminTools");
            if (adminTools) adminTools.style.display = "none";
            if (window.updateUploadUI) window.updateUploadUI();
        }
    }

    // 通知轮询
    var notificationIntervalId = null;

    function startNotificationPolling() {
        // 避免重复启动
        if (notificationIntervalId) return;

        // 立即检查一次
        checkNotifications();

        // 每 30 秒检查一次
        notificationIntervalId = setInterval(checkNotifications, 30000);
    }

    async function checkNotifications() {
        var token = localStorage.getItem("token");
        if (!token) return;

        try {
            var res = await fetch("/api/notifications?unread=true", {
                headers: { "Authorization": "Bearer " + token }
            });
            var data = await res.json();

            if (data.notifications && data.notifications.length > 0) {
                data.notifications.forEach(function (n) {
                    // 显示通知
                    if (window.showToast) {
                        var type = n.type === "moderation_reject" ? "error" : "warning";
                        window.showToast(n.message, type);
                    }

                    // 标记为已读
                    fetch("/api/notifications/" + n.id + "/read", {
                        method: "POST",
                        headers: { "Authorization": "Bearer " + token }
                    });
                });
            }
        } catch (e) {
            console.warn("检查通知失败", e);
        }
    }

    function showUserInfo() {
        if (authForm) authForm.style.display = "none";
        if (authUserInfo) authUserInfo.style.display = "block";
        if (authTitle) authTitle.innerText = "用户信息";
        if (currentUserDisplay) currentUserDisplay.innerText = username;
        // Ensure no overlap
        updateModalLayout();
        // Load stats whenever info is shown
        if (typeof loadUserStats === 'function') {
            loadUserStats();
        }
    }

    function showLoginForm() {
        currentAuthMode = 'login';
        if (authUserInfo) authUserInfo.style.display = "none";
        if (authForm) authForm.style.display = "block";
        updateModalLayout();
        updateModalUI();
    }

    // Helper to force layout check (optional, but good for safety)
    function updateModalLayout() {
        // Double check visibility
        if (token && authUserInfo && authUserInfo.style.display !== "block") {
            authForm.style.display = "none";
            authUserInfo.style.display = "block";
        } else if (!token && authForm && authForm.style.display !== "block") {
            authUserInfo.style.display = "none";
            authForm.style.display = "block";
        }
    }

    function updateModalUI() {
        resetMsg();
        var googleBtn = document.getElementById("googleBtnContainer");

        if (currentAuthMode === 'login') {
            if (authTitle) authTitle.innerText = "登录";
            if (authSubmitBtn) authSubmitBtn.innerText = "登录";
            if (authToggleText) authToggleText.innerText = "还没有账号？";
            if (authToggleLink) {
                authToggleLink.innerText = "去注册";
                authToggleLink.style.display = "inline";
            }

            if (emailGroup) emailGroup.style.display = "none";
            if (codeGroup) codeGroup.style.display = "none";
            if (captchaGroup) captchaGroup.style.display = "none";  // 登录隐藏验证码
            if (passwordHint) passwordHint.style.display = "none";
            if (forgotPasswordLink) forgotPasswordLink.style.display = "inline";
            if (authUsernameInput) authUsernameInput.parentNode.style.display = "block";
            if (authPasswordInput) authPasswordInput.parentNode.parentNode.style.display = "block"; // form-group
            if (rememberMeGroup) rememberMeGroup.style.display = "flex";

            if (googleBtn) {
                googleBtn.style.display = "flex";
                if (window.google) {
                    // Fetch Client ID from backend config
                    fetch("/auth/config")
                        .then(res => res.json())
                        .then(config => {
                            if (config.google_client_id) {
                                google.accounts.id.initialize({
                                    client_id: config.google_client_id,
                                    callback: handleGoogleCredentialResponse,
                                    // [Fix] 使用 redirect 模式，避免 COOP 弹窗问题
                                    // redirect 模式不依赖 postMessage，完全绕过跨域隔离问题
                                    ux_mode: "redirect",
                                    login_uri: window.location.origin + "/auth/google-callback"
                                });
                                google.accounts.id.renderButton(
                                    googleBtn,
                                    { theme: "outline", size: "large", width: "100%" }
                                );
                            } else {
                                // console.warn("Google Client ID not configured");
                                // googleBtn.innerHTML = "<span style='font-size:12px;color:gray'>Google Login 未配置</span>";
                            }
                        })
                        .catch(err => console.error(err));
                }
            }

        } else if (currentAuthMode === 'register') {
            if (authTitle) authTitle.innerText = "注册";
            if (authSubmitBtn) authSubmitBtn.innerText = "注册";
            if (authToggleText) authToggleText.innerText = "已有账号？";
            if (authToggleLink) {
                authToggleLink.innerText = "去登录";
                authToggleLink.style.display = "inline";
            }

            if (emailGroup) emailGroup.style.display = "block";
            if (codeGroup) codeGroup.style.display = "block";
            if (passwordHint) passwordHint.style.display = "block";
            if (forgotPasswordLink) forgotPasswordLink.style.display = "none";
            if (authUsernameInput) authUsernameInput.parentNode.style.display = "block";
            if (authPasswordInput) authPasswordInput.parentNode.parentNode.style.display = "block";
            if (rememberMeGroup) rememberMeGroup.style.display = "none";
            if (captchaGroup) captchaGroup.style.display = "block";  // 注册显示验证码
            loadCaptcha();  // 加载验证码图片

            if (googleBtn) googleBtn.style.display = "none";

        } else if (currentAuthMode === 'reset') {
            if (authTitle) authTitle.innerText = "重置密码";
            if (authSubmitBtn) authSubmitBtn.innerText = "重置密码";
            if (authToggleText) authToggleText.innerText = "想起密码了？";
            if (authToggleLink) {
                authToggleLink.innerText = "去登录";
                authToggleLink.style.display = "inline";
            }

            if (emailGroup) emailGroup.style.display = "block";
            if (codeGroup) codeGroup.style.display = "block";
            if (passwordHint) passwordHint.style.display = "block"; // 提示新密码
            if (forgotPasswordLink) forgotPasswordLink.style.display = "none";

            // Hide Username input for reset
            if (authUsernameInput) authUsernameInput.parentNode.style.display = "none";
            if (authPasswordInput) authPasswordInput.parentNode.parentNode.style.display = "block";
            if (rememberMeGroup) rememberMeGroup.style.display = "none";
            if (captchaGroup) captchaGroup.style.display = "none";  // 重置密码隐藏验证码

            if (googleBtn) googleBtn.style.display = "none";
        }
    }

    var countdown = 0;
    async function handleSendCode() {
        var email = authEmailInput.value.trim();
        if (!email) {
            if (authMessage) authMessage.innerText = "请输入邮箱";
            return;
        }
        if (!/^\S+@\S+\.\S+$/.test(email)) {
            if (authMessage) authMessage.innerText = "邮箱格式不正确";
            return;
        }
        if (countdown > 0) return;

        try {
            sendCodeBtn.disabled = true;
            sendCodeBtn.innerText = "发送中...";

            var type = (currentAuthMode === 'register') ? 'register' : 'reset';

            var res = await fetch("/auth/send-code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: email, type: type })
            });
            var data = await res.json();

            if (res.ok) {
                if (window.showToast) window.showToast("验证码已发送", "success");
                startCountdown(60);
            } else {
                if (authMessage) authMessage.innerText = data.detail || "发送失败";
                sendCodeBtn.disabled = false;
                sendCodeBtn.innerText = "发送验证码";
            }
        } catch (e) {
            console.error(e);
            if (authMessage) authMessage.innerText = "网络错误";
            sendCodeBtn.disabled = false;
            sendCodeBtn.innerText = "发送验证码";
        }
    }

    function startCountdown(seconds) {
        countdown = seconds;
        sendCodeBtn.disabled = true;

        var timer = setInterval(function () {
            countdown--;
            sendCodeBtn.innerText = countdown + "s";
            if (countdown <= 0) {
                clearInterval(timer);
                sendCodeBtn.disabled = false;
                sendCodeBtn.innerText = "发送验证码";
            }
        }, 1000);
    }

    // Google Login Callback
    window.handleGoogleCredentialResponse = async function (response) {
        try {
            var res = await fetch("/auth/google", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: response.credential })
            });
            var data = await res.json();

            if (res.ok) {
                token = data.access_token;
                username = data.username;
                localStorage.setItem("token", token);
                localStorage.setItem("username", username);

                checkLoginStatus();
                authModal.style.display = "none";
                if (window.showToast) window.showToast("Google 登录成功", "success");
                if (window.displayHistory) window.displayHistory();
            } else {
                if (authMessage) authMessage.innerText = data.detail || "Google 登录失败";
            }
        } catch (e) {
            console.error(e);
            if (authMessage) authMessage.innerText = "网络错误";
        }
    }

    function resetForm() {
        if (authUsernameInput) authUsernameInput.value = "";
        if (authPasswordInput) authPasswordInput.value = "";
        if (authEmailInput) authEmailInput.value = "";
        if (authCodeInput) authCodeInput.value = "";
        resetMsg();
    }

    function resetMsg() {
        if (authMessage) authMessage.innerText = "";
    }

    async function handleAuthSubmit() {
        var user = authUsernameInput.value.trim();
        var pass = authPasswordInput.value.trim();
        var email = authEmailInput ? authEmailInput.value.trim() : "";
        var code = authCodeInput ? authCodeInput.value.trim() : "";

        if (currentAuthMode === 'login') {
            if (!user || !pass) {
                if (authMessage) authMessage.innerText = "请输入用户名和密码";
                return;
            }
        } else if (currentAuthMode === 'register') {
            // 调试模式下跳过邮箱验证
            var skipEmailCheck = (typeof isDebugMode !== 'undefined' && isDebugMode);

            if (!user || !pass || (!skipEmailCheck && (!email || !code))) {
                if (authMessage) authMessage.innerText = "请填写所有字段";
                return;
            }
        } else if (currentAuthMode === 'reset') {
            if (!email || !code || !pass) {
                if (authMessage) authMessage.innerText = "请填写所有字段";
                return;
            }
        }

        var endpoint = "";
        var body;
        var headers = {};

        if (currentAuthMode === 'login') {
            var rememberMe = authRememberMe ? authRememberMe.checked : true;
            endpoint = "/auth/login?remember_me=" + rememberMe;
            body = new FormData();
            body.append("username", user);
            body.append("password", pass);
        } else if (currentAuthMode === 'register') {
            // 获取验证码输入
            var captchaCode = captchaInput ? captchaInput.value.trim() : '';
            var skipEmailCheck = (typeof isDebugMode !== 'undefined' && isDebugMode);

            if (skipEmailCheck) {
                // 🔧 调试模式：使用简单注册端点（只需用户名+密码+图形验证码）
                endpoint = "/auth/register";
                body = JSON.stringify({
                    username: user,
                    password: pass,
                    captcha_id: currentCaptchaId || '',
                    captcha_code: captchaCode
                });
            } else {
                // 生产模式：使用邮箱注册端点
                endpoint = "/auth/register-email";
                body = JSON.stringify({
                    username: user,
                    password: pass,
                    email: email,
                    code: code,
                    captcha_id: currentCaptchaId || '',
                    captcha_code: captchaCode
                });
            }
            headers["Content-Type"] = "application/json";
        } else if (currentAuthMode === 'reset') {
            endpoint = "/auth/reset-password";
            body = JSON.stringify({
                email: email,
                code: code,
                new_password: pass
            });
            headers["Content-Type"] = "application/json";
        }

        try {
            authSubmitBtn.disabled = true;
            var res = await fetch(endpoint, {
                method: "POST",
                headers: headers,
                body: body
            });
            var data = await res.json();
            authSubmitBtn.disabled = false;

            if (res.ok) {
                if (currentAuthMode === 'login') {
                    handleLoginSuccess(data);
                } else if (currentAuthMode === 'register') {
                    // 注册成功后自动登录（后端现在返回 token）
                    if (data.access_token) {
                        handleLoginSuccess(data);
                        if (window.showToast) window.showToast("注册成功", "success");
                    } else {
                        // 兼容旧逻辑
                        if (window.showToast) window.showToast("注册成功，请登录", "success");
                        currentAuthMode = 'login';
                        updateModalUI();
                        authUsernameInput.value = user;
                    }
                } else if (currentAuthMode === 'reset') {
                    if (window.showToast) window.showToast("密码重置成功，请登录", "success");
                    currentAuthMode = 'login';
                    updateModalUI();
                }
            } else {
                if (authMessage) authMessage.innerText = data.detail || "操作失败";
            }
        } catch (e) {
            console.error(e);
            authSubmitBtn.disabled = false;
            if (authMessage) authMessage.innerText = "系统错误: " + e.message;
        }
    }

    function handleLoginSuccess(data) {
        token = data.access_token;
        username = data.username;
        localStorage.setItem("token", token);
        localStorage.setItem("username", username);
        // [FIX] 存储 VIP 和 Admin 状态
        localStorage.setItem("is_vip", data.is_vip === true ? 'true' : 'false');
        localStorage.setItem("is_admin", data.is_admin === true ? 'true' : 'false');

        checkLoginStatus();
        authModal.style.display = "none";
        if (window.showToast) window.showToast("登录成功", "success");
        if (window.displayHistory) window.displayHistory();
    }

    function handleLogout() {
        localStorage.removeItem("token");
        localStorage.removeItem("username");
        localStorage.removeItem("is_vip");
        localStorage.removeItem("is_admin");
        token = null;
        username = null;
        window.currentUser = null;
        checkLoginStatus();
        authModal.style.display = "none";
        if (window.showToast) window.showToast("已退出登录", "info");

        // Refresh history to clear private data potentially
        if (window.displayHistory) window.displayHistory();
    }

    // ========== 账号管理功能 ==========
    var changeUsernameBtn = document.getElementById("changeUsernameBtn");
    var changePasswordBtn = document.getElementById("changePasswordBtn");
    var deleteAccountLink = document.getElementById("deleteAccountLink");
    var userEmailDisplay = document.getElementById("userEmailDisplay");
    var userStatsDisplay = document.getElementById("userStatsDisplay");
    var activateVipBtn = document.getElementById("activateVipBtn");

    // VIP 激活
    if (activateVipBtn) {
        activateVipBtn.onclick = function () {
            showInputModal(
                "💎 激活 VIP",
                "请输入您的 VIP 激活码:",
                [{ id: "vip_code", placeholder: "XXXX-XXXX-XXXX-XXXX" }],
                async (values, close) => {
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
                                "Authorization": "Bearer " + token
                            },
                            body: JSON.stringify({ code: code.trim() })
                        });
                        var data = await res.json();

                        if (res.ok) {
                            if (window.showToast) window.showToast("VIP 激活成功！有效期至: " + data.expiry, "success");
                            checkLoginStatus(); // 刷新状态
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

    // [Admin] 上帝视角审计按钮
    var adminAuditBtn = document.getElementById("adminAuditBtn");
    if (adminAuditBtn) {
        adminAuditBtn.onclick = function () {
            // 1. 关闭设置模态框
            if (document.getElementById("settingsModal")) {
                document.getElementById("settingsModal").style.display = "none";
            }
            // 2. 切换到历史记录 Tab
            var tabHistory = document.getElementById("tab-history");
            if (tabHistory) tabHistory.click();

            // 3. 强制触发 history.js 的加载逻辑 (通过某种全局变量或直接操作)
            // 这里我们设置一个临时全局标记，history.js 会读取它
            if (window.forceAdminAuditMode) {
                window.forceAdminAuditMode();
            } else {
                alert("审计功能未就绪，请刷新页面重试");
            }
        };
    }

    // [Admin] 批量生成激活码按钮
    var generateVipCodesBtn = document.getElementById("generateVipCodesBtn");
    if (generateVipCodesBtn) {
        generateVipCodesBtn.onclick = function () {
            showInputModal(
                "📥 批量生成激活码",
                "请输入生成数量和天数:",
                [
                    { id: "vip_days", label: "有效期(天)", value: "30", type: "number" },
                    { id: "vip_count", label: "生成数量(个)", value: "10", type: "number" }
                ],
                async (values, close) => {
                    var days = parseInt(values.vip_days);
                    var count = parseInt(values.vip_count);

                    if (!days || days <= 0 || !count || count <= 0) {
                        alert("请输入有效的数字");
                        return;
                    }

                    try {
                        // 使用 Form Data 提交，匹配后端 endpoints
                        var formData = new FormData();
                        formData.append("days", days);
                        formData.append("count", count);

                        var res = await fetch("/admin/vip/generate", {
                            method: "POST",
                            headers: {
                                "Authorization": "Bearer " + token
                            },
                            body: formData
                        });
                        var data = await res.json();

                        if (res.ok && data.success) {
                            // 生成成功，弹窗显示结果或者下载文件
                            var codes = data.codes;
                            if (codes && codes.length > 0) {
                                // 创建一个临时文本区域供复制
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

    // 加载用户统计信息
    async function loadUserStats() {
        if (!token) return;
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
                    var vipInfo = stats.is_vip ? ("VIP到期: " + stats.vip_expiry.split("T")[0]) : "普通用户";
                    userStatsDisplay.innerHTML = `注册: ${stats.created_at.split("T")[0]} | 上传: ${stats.upload_count} | ${vipInfo}`;
                }
            }
        } catch (e) {
            console.error("加载统计失败", e);
        }
    }


    // Generic Input Modal Helper
    function showInputModal(title, message, inputs, callback) {
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
        inputs.forEach(cfg => {
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
            input.className = "form-control"; // reuse existing class
            input.style.width = "100%";
            input.id = cfg.id;
            div.appendChild(input);
            container.appendChild(div);
        });

        // Handlers
        var closeModal = () => {
            modal.style.display = "none";
            // clear handlers to prevent leaks/duplication
            submitBtn.onclick = null;
        };

        submitBtn.onclick = () => {
            var values = {};
            inputs.forEach(cfg => {
                var el = document.getElementById(cfg.id);
                values[cfg.id] = el ? el.value : "";
            });
            callback(values, closeModal);
        };

        cancelBtn.onclick = closeModal;
        closeBtn.onclick = closeModal;

        modal.style.display = "flex";
    }

    // 修改用户名
    if (changeUsernameBtn) {
        changeUsernameBtn.onclick = function () {
            showInputModal(
                "修改用户名",
                "请输入新的用户名 (2-20个字符):",
                [{ id: "new_username", value: username, placeholder: "新用户名" }],
                async (values, close) => {
                    var newName = values.new_username;
                    if (!newName || newName.trim() === "" || newName === username) {
                        alert("无效的用户名");
                        return;
                    }

                    try {
                        var res = await fetch("/auth/change-username", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer " + token
                            },
                            body: JSON.stringify({ new_username: newName.trim() })
                        });
                        var data = await res.json();

                        if (res.ok && data.access_token) {
                            token = data.access_token;
                            username = data.username;
                            localStorage.setItem("token", token);
                            localStorage.setItem("username", username);

                            if (currentUserDisplay) currentUserDisplay.innerText = username;
                            if (window.showToast) window.showToast("用户名修改成功", "success");
                            checkLoginStatus();
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

    // 修改密码
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
                async (values, close) => {
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
                                "Authorization": "Bearer " + token
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


    // Settings Logic
    var settingsBtn = document.getElementById("settingsBtn");
    var settingsModal = document.getElementById("settingsModal");
    var debugModeToggle = document.getElementById("debugModeToggle");
    var isDebugMode = false;

    // Load settings on start
    loadSystemSettings();

    async function loadSystemSettings() {
        try {
            var res = await fetch("/system/settings");
            if (res.ok) {
                var settings = await res.json();
                isDebugMode = settings.debug_mode || false;
                if (debugModeToggle) debugModeToggle.checked = isDebugMode;
                console.log("Debug Mode:", isDebugMode);
            }
        } catch (e) {
            console.error("Failed to load settings", e);
        }
    }

    if (settingsBtn) {
        settingsBtn.onclick = function () {
            if (settingsModal) settingsModal.style.display = "flex";
        }
    }

    // Close Settings Modal
    var settingsModalCloseBtn = document.getElementById("settingsModalCloseBtn");
    if (settingsModalCloseBtn) {
        settingsModalCloseBtn.onclick = function () {
            if (settingsModal) settingsModal.style.display = "none";
        }
    }

    // Click outside to close settings modal
    if (settingsModal) {
        settingsModal.addEventListener('click', function (e) {
            if (e.target === settingsModal) {
                settingsModal.style.display = "none";
            }
        });
    }

    if (debugModeToggle) {
        debugModeToggle.onchange = async function () {
            var newValue = this.checked;
            try {
                var res = await fetch("/system/settings", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ debug_mode: newValue })
                });
                if (res.ok) {
                    var data = await res.json();
                    isDebugMode = data.debug_mode;
                    if (window.showToast) window.showToast("调试模式已" + (isDebugMode ? "开启" : "关闭"), "success");
                    // Refresh UI if register modal is open
                    updateModalUI();
                }
            } catch (e) {
                console.error(e);
                this.checked = !newValue; // Revert
                alert("设置保存失败");
            }
        }
    }

    // Override updateModalUI to handle debug mode visibility
    var originalUpdateModalUI = updateModalUI;
    updateModalUI = function () {
        // Call original to set basic state (restores Google Login etc)
        if (typeof originalUpdateModalUI === 'function') originalUpdateModalUI();

        // Apply Debug Mode overrides
        if (currentAuthMode === 'register') {
            var emailInput = document.getElementById("email");
            var codeInput = document.getElementById("code");
            var emailGroup = document.getElementById("emailGroup");
            var codeGroup = document.getElementById("codeGroup");

            if (isDebugMode) {
                if (emailGroup) emailGroup.style.display = "none";
                if (codeGroup) codeGroup.style.display = "none";
                if (emailInput) emailInput.removeAttribute("required");
                if (codeInput) codeInput.removeAttribute("required");
            } else {
                if (emailGroup) emailGroup.style.display = "block";
                if (codeGroup) codeGroup.style.display = "block";
                if (emailInput) emailInput.setAttribute("required", "true");
                if (codeInput) codeInput.setAttribute("required", "true");
            }
        }
    };




    // 注销账号 - Fixed: Removed native confirm
    if (deleteAccountLink) {
        deleteAccountLink.onclick = function () {
            // 直接显示自定义弹窗，不使用 confirm()
            showInputModal(
                "确认注销账号",
                "此操作不可恢复！请输入 invalid \"DELETE\" 以确认注销:",
                [{ id: "confirm_text", placeholder: "DELETE" }],
                async (values, close) => {
                    if (values.confirm_text !== "DELETE") {
                        alert("输入错误，取消注销");
                        return;
                    }
                    try {
                        var res = await fetch("/auth/delete-account", {
                            method: "DELETE",
                            headers: { "Authorization": "Bearer " + token }
                        });
                        var data = await res.json();

                        if (res.ok) {
                            if (window.showToast) window.showToast("账号已注销", "info");
                            handleLogout();
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


    // 设备管理 (原登录日志)
    var viewSessionsBtn = document.getElementById("viewSessionsBtn");
    var sessionsModal = document.getElementById("sessionsModal");
    var sessionsTableBody = document.getElementById("sessionsTableBody");

    function parseJwt(token) {
        try {
            var base64Url = token.split('.')[1];
            var base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            var jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function (c) {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join(''));
            return JSON.parse(jsonPayload);
        } catch (e) {
            return {};
        }
    }

    if (viewSessionsBtn) {
        viewSessionsBtn.onclick = async function () {
            if (!token) return;
            if (sessionsModal) sessionsModal.style.display = "flex";
            if (sessionsTableBody) sessionsTableBody.innerHTML = "<tr><td colspan='4' style='padding:10px;text-align:center'>加载中...</td></tr>";

            // Identify current session
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

                            // Simple UA parsing
                            var deviceName = "未知设备";
                            if (ua.includes("Windows")) deviceName = "🖥️ Windows PC";
                            else if (ua.includes("Mac")) deviceName = "💻 Mac";
                            else if (ua.includes("Android")) deviceName = "📱 Android";
                            else if (ua.includes("iPhone")) deviceName = "📱 iPhone";
                            else if (ua.includes("Linux")) deviceName = "🐧 Linux";
                            else deviceName = "🌐 浏览器";

                            if (isCurrent) deviceName += " (当前设备)";

                            var lastActive = session.last_active;
                            try {
                                var date = new Date(session.last_active + "Z");
                                if (!isNaN(date)) lastActive = date.toLocaleString();
                            } catch (e) { }

                            var actionHtml = "";
                            if (isCurrent) {
                                actionHtml = "<span style='color:green;font-size:12px;'>在线</span>";
                            } else {
                                actionHtml = `<button class='btn-mini btn-danger' onclick='window.revokeSession("${session.session_id}")'>下线</button>`;
                            }

                            tr.innerHTML = `
                                <td style="padding: 8px;">
                                    <div style="font-weight:bold">${deviceName}</div>
                                    <div style="font-size:11px;color:#999;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${ua}">${ua}</div>
                                </td>
                                <td style="padding: 8px;">${session.ip_address}</td>
                                <td style="padding: 8px;">${lastActive}</td>
                                <td style="padding: 8px; text-align: right;">${actionHtml}</td>
                            `;
                            sessionsTableBody.appendChild(tr);
                        });
                    }
                }
            } catch (e) {
                console.error(e);
                if (sessionsTableBody) sessionsTableBody.innerHTML = "<tr><td colspan='4' style='padding:10px;text-align:center;color:red'>加载失败</td></tr>";
            }
        };
    }

    // Global function for Revoke
    window.revokeSession = async function (sid) {
        if (!confirm("确定要强制该设备下线吗？")) return;

        try {
            var res = await fetch("/auth/sessions/" + sid, {
                method: "DELETE",
                headers: { "Authorization": "Bearer " + token }
            });
            if (res.ok) {
                if (window.showToast) window.showToast("已强制下线", "success");
                // Reload list
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
