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

    // 🔧 调试模式状态 (使用全局变量)
    // var isDebugMode = false; // Removed in favor of window.isDebugMode


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
        var guestTools = document.getElementById("guestTools");
        var userMenuContainer = document.getElementById("userMenuContainer");

        // Elements in Header
        var headerUserName = document.getElementById("headerUserName");
        var headerUserAvatar = document.getElementById("headerUserAvatar");
        var userMenuTrigger = document.getElementById("userMenuTrigger");

        // Elements in Dropdown
        var dropdownUserName = document.getElementById("dropdownUserName");
        var dropdownUserEmail = document.getElementById("dropdownUserEmail");
        var dropdownVipBadge = document.getElementById("dropdownVipBadge");
        var dropdownAdminLink = document.getElementById("dropdownAdminLink");
        var dropdownSettingsBtn = document.getElementById("dropdownSettingsBtn"); // Account Settings
        var dropdownLogoutBtn = document.getElementById("dropdownLogoutBtn");


        if (token && username) {
            // ============ LOGGED IN ============
            if (guestTools) guestTools.style.display = "none";
            if (userMenuContainer) userMenuContainer.style.display = "block";

            // Basic Display
            if (headerUserName) headerUserName.innerText = username;
            if (dropdownUserName) dropdownUserName.innerText = username;

            // Avatar Placeholder (Real avatar loaded from /auth/me)
            if (headerUserAvatar && !headerUserAvatar.src) {
                // Keep existing or default
            }

            // Bind Dropdown Trigger
            if (userMenuTrigger) {
                userMenuTrigger.onclick = function (e) {
                    e.stopPropagation(); // Prevent immediate closing
                    if (window.toggleUserMenu) window.toggleUserMenu();
                };
            }

            // Bind Dropdown Actions
            if (dropdownSettingsBtn) {
                dropdownSettingsBtn.onclick = function () {
                    // Open the original User Info Modal which has all settings
                    if (authModal) authModal.style.display = "flex";
                    showUserInfo();
                    // Close dropdown
                    if (window.toggleUserMenu) {
                        var menu = document.getElementById('userDropdown');
                        if (menu) menu.style.display = 'none';
                        if (userMenuTrigger) userMenuTrigger.classList.remove('active');
                    }
                };
            }

            if (dropdownLogoutBtn) {
                dropdownLogoutBtn.onclick = handleLogout;
            }

            // Verify Token & Get Details
            try {
                var res = await fetch("/auth/me", {
                    headers: { "Authorization": "Bearer " + token }
                });
                if (res.ok) {
                    var user = await res.json();

                    // Sync Storage
                    localStorage.setItem("is_vip", user.is_vip === true ? 'true' : 'false');
                    localStorage.setItem("is_admin", user.is_admin === true ? 'true' : 'false');
                    window.currentUser = user;

                    // Update UI with details
                    var fallbackAvatar = document.getElementById("headerUserAvatarFallback");

                    if (headerUserAvatar) {
                        if (user.avatar) {
                            headerUserAvatar.src = user.avatar;
                            headerUserAvatar.style.display = 'block';
                            if (fallbackAvatar) fallbackAvatar.style.display = 'none';

                            // Re-bind error handler to show fallback if load fails
                            headerUserAvatar.onerror = function () {
                                this.style.display = 'none';
                                if (fallbackAvatar) fallbackAvatar.style.display = 'flex'; // Flex for centering SVG
                            };
                        } else {
                            // No avatar set -> Show fallback
                            headerUserAvatar.style.display = 'none';
                            if (fallbackAvatar) fallbackAvatar.style.display = 'flex';
                        }
                    }
                    if (dropdownUserEmail) {
                        dropdownUserEmail.innerText = user.email || (user.is_admin ? "管理员" : "普通用户");
                    }

                    // VIP Badge (Dropdown + Header)
                    var headerVipBadge = document.getElementById("headerVipBadge");
                    var upgradeVipBtn = document.getElementById("upgradeVipBtn");

                    if (dropdownVipBadge) {
                        dropdownVipBadge.style.display = user.is_vip ? "inline-block" : "none";
                    }
                    if (headerVipBadge) {
                        headerVipBadge.style.display = user.is_vip ? "inline-block" : "none";
                    }

                    // Hide "Upgrade VIP" btn if user is already VIP
                    if (upgradeVipBtn) {
                        if (user.is_vip) upgradeVipBtn.style.display = "none";
                        // else upgradeVipBtn.style.display = "flex"; // Optional: keep it visible or not? 
                        // Usually keep it visible for non-VIP logged in users
                    }

                    // Admin Link

                    // Admin Link
                    if (dropdownAdminLink) {
                        dropdownAdminLink.style.display = user.is_admin ? "flex" : "none";
                    }

                    // Also show/hide Admin Tools in the User Info Modal (legacy/backup)
                    var adminTools = document.getElementById("adminTools");
                    if (adminTools) {
                        adminTools.style.display = user.is_admin ? "block" : "none";
                    }

                    // [NEW] Update Upload UI based on private mode preference if saved?
                    // actually updateUploadUI handles its own state, but we might want to refresh it.
                    if (window.updateUploadUI) window.updateUploadUI();

                    startNotificationPolling();
                } else {
                    handleLogout();
                }
            } catch (e) {
                console.error("Auth check failed", e);
            }
        } else {
            // ============ GUEST ============
            if (guestTools) guestTools.style.display = "flex";
            if (userMenuContainer) userMenuContainer.style.display = "none";

            window.currentUser = null;
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
        if (typeof window.loadUserStats === 'function') {
            window.loadUserStats();
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
                                    // [Restore] 听主人的话，改回跳转模式 (Redirect Mode)
                                    // 请确保 Google Console 中的 "Authorized redirect URIs" 包含:
                                    // window.location.origin + "/auth/google-callback"
                                    ux_mode: "redirect",
                                    login_uri: window.location.origin + "/auth/google-callback",
                                    // callback: handleGoogleCredentialResponse // redirect 模式不需要 callback
                                });
                                console.log("Google Login URI (Redirect):", window.location.origin + "/auth/google-callback");
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

            // 🔧 调试模式下隐藏验证码和邮箱验证喵~
            var skipEmailCheck = (typeof window.isDebugMode !== 'undefined' && window.isDebugMode);
            if (skipEmailCheck) {
                if (captchaGroup) captchaGroup.style.display = "none";
                // Debug Mode: Hide email/code inputs
                if (emailGroup) emailGroup.style.display = "none";
                if (codeGroup) codeGroup.style.display = "none";
                if (authEmailInput) authEmailInput.removeAttribute("required");
                if (authCodeInput) authCodeInput.removeAttribute("required");
                if (captchaInput) captchaInput.removeAttribute("required");
            } else {
                if (captchaGroup) captchaGroup.style.display = "block";
                if (emailGroup) emailGroup.style.display = "block";
                if (codeGroup) codeGroup.style.display = "block";
                if (authEmailInput) authEmailInput.setAttribute("required", "true");
                if (authCodeInput) authCodeInput.setAttribute("required", "true");
                loadCaptcha();  // 加载验证码图片
            }

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
            var skipEmailCheck = (typeof window.isDebugMode !== 'undefined' && window.isDebugMode);

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
            var skipEmailCheck = (typeof window.isDebugMode !== 'undefined' && window.isDebugMode);

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








    // ==================== 暴露共享函数到 window 对象 ====================
    // 🔧 让拆分后的模块可以调用这些函数喵~
    window.checkLoginStatus = checkLoginStatus;
    window.handleLogout = handleLogout;
    // window.showInputModal = showInputModal; // Already in ui.js
    window.updateModalUI = updateModalUI;
});
