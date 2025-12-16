"use strict";

// core.js - 全局初始化入口与核心工具

window.onload = function () {
    // 初始化 UI (标签切换等)
    if (typeof initUI === 'function') initUI();

    // 初始化上传模块
    if (typeof initUpload === 'function') initUpload();

    // 初始化粘贴模块
    if (typeof initPaste === 'function') initPaste();

    // 初始化历史记录 (由 history.js 自动处理)
    // if (typeof initHistory === 'function') {
    //     initHistory();
    // }

    console.log("App initialized.");
};

// ===================================
// 分享模态框逻辑 (Share Modal)
// ===================================

// 显示分享模态框
window.openShareModal = async function (itemData) {
    var modal = document.getElementById('shareModal');
    if (!modal) return;

    // 1. 设置基础信息
    var thumb = document.getElementById('shareModalThumb');
    var nameEl = document.getElementById('shareModalName');
    var sizeEl = document.getElementById('shareModalSize');
    var vipBadge = document.getElementById('shareModalVipBadge');

    // 缩略图: 优先使用 thumb_url, 其次 url, 最后默认
    thumb.src = itemData.thumb_url || itemData.url || '/static/img/file_icon.png';
    nameEl.innerText = itemData.filename || '未命名图片';
    // 如果有 size 字段 (格式化后的字符串 或 字节数)
    if (itemData.size) {
        sizeEl.innerText = isNaN(itemData.size) ? itemData.size : formatSize(itemData.size);
    } else {
        sizeEl.innerText = '未知大小';
    }

    // 2. 检查权限
    var token = localStorage.getItem('token');
    var isVip = localStorage.getItem('is_vip') === 'true';
    var isLoggedIn = !!token;

    // 显示/隐藏 VIP Badge
    if (vipBadge) vipBadge.style.display = isVip ? 'block' : 'none';

    // 3. 生成链接
    // View URL: 永远是 /view/{hash} 或 /view/{filename} (如果 filename 是 hash)
    // 我们的 itemData.url 通常是 /mycloud/path/to/file.ext (raw)
    // itemData.viewUrl 可能是已经在 upload.js 计算好的

    // 如果没有预计算 viewUrl, 我们尝试推导:
    // 假设 itemData.url = /mycloud/2023/12/15/hash.jpg
    // Landing Page URL 应该是 /view/hash (我们需要 hash)

    var viewUrl = itemData.viewUrl;
    if (!viewUrl && itemData.hash) {
        // 自动构建
        viewUrl = window.location.origin + '/view/' + itemData.hash;
    } else if (!viewUrl) {
        // Fallback: 如果没有 hash, 暂时用 raw url (虽然不理想)
        viewUrl = itemData.url;
    }

    // Raw URL: 原始的直链路径 (无签名)
    var rawPath = itemData.url;
    if (rawPath.startsWith('http')) {
        // 如果后端返回了完整 URL (例如 s3 代理), 我们需要提取路径部分
        try {
            var u = new URL(rawPath);
            rawPath = u.pathname; // /mycloud/...
        } catch (e) { }
    }

    // 4. 填充输入框

    // [1] 查看链接 (所有用户)
    document.getElementById('shareLinkView').value = viewUrl;

    // [2] HTML (所有用户)
    var htmlCode = `<a href="${viewUrl}" target="_blank"><img src="${viewUrl}" alt="${itemData.filename}"></a>`;
    // 注意: 在 HTML 中直接引用 viewUrl 作为 img src 通常会获得 404 或 html 页面，导致裂图。
    // Landing Page 模式下，img src 应该是缩略图或者 raw url (如果公开)。
    // 为了稳妥，HTML 代码应该指向 Landing Page，显示的图片应该是缩略图 (如果有) 或 占位符。
    // 更佳实践: <a href="viewUrl"><img src="thumbUrl"></a>
    var thumbUrl = itemData.thumb_url || itemData.url; // 暂时用 raw url 作为缩略图 (虽然可能防盗链)
    // 如果是私有图片，raw url 也是 403 的。
    // 所以对于 Guest/User，HTML 代码里的 img src 其实很难弄，除非我们有一个公开的缩略图接口。
    // 暂时：使用 ViewUrl (虽然可能裂图) 或者 仅文字链接?
    // PostImages 做法: Markdown 里的图片链接是直链(或缩略图直链)。
    // 我们的情况：图片默认私有。
    // 妥协方案: 对于 HTML/Markdown，如果不提供签名，只能显示 View Link。
    // img src = "/static/img/locked.png" ?
    // 让我们简化： HTML 代码 = <a href="${viewUrl}">查看图片</a> (如果是私有且非VIP)
    // 如果用户是 VIP，我们可以生成带签名的 thumb url。

    // 重新设计策略:
    // Guest: 只能复制 View Link. 
    // HTML/Markdown 选项对 Guest 隐藏或仅提供 View Link (无图)。
    // User: Markdown = [![Image](thumbUrl)](viewUrl) -> thumbUrl 必须可访问。
    // 问题：私有图片的 thumbUrl 也是受保护的吗？通常缩略图也应该受保护。
    // 除非我们有一个 /thumb/{hash} 接口是公开的？目前没有。
    // 现有逻辑：私有图片必须签名。
    // 所以，对于非 VIP 用户，无法生成可显示的图片代码！
    // 除非：我们允许“低分辨率缩略图”公开访问？
    // 或者：Markdown 代码仅包含链接 `[查看图片](viewUrl)`。

    // [恢复] 变量定义
    var rawContainer = document.getElementById('shareRawContainer');
    var rawVipTip = document.getElementById('shareRawVipTip');
    var mdGuestTip = document.getElementById('shareMdGuestTip');

    // 异步获取签名直链 (如果需要)
    var imgSrcPromise = Promise.resolve(null);
    var isShared = false; // 无法直接从 itemData 判断是否共享(缺少字段?) 
    // 实际上 itemData 来自 history/upload, 应该包含 is_shared 或者是通过 viewMode 判断
    // 但这里最稳妥的是：如果是 VIP，生成签名链；如果不是 VIP，检查是否能访问直链？
    // 简化策略: 
    // VIP -> 获取签名链用于 Markdown/HTML
    // 非 VIP -> 使用原始链接 (如果是私有会裂图，但如果是共享则正常)

    if (isVip) {
        rawContainer.style.display = 'flex';
        rawVipTip.style.display = 'none';

        // 请求签名
        var path = rawPath.startsWith("/mycloud/") ? rawPath.substring(9) : rawPath;
        if (path.startsWith("/")) path = path.substring(1);

        imgSrcPromise = fetch('/auth/sign-url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ object_name: path })
        }).then(res => res.ok ? res.json() : null)
            .then(data => data ? data.signed_url : itemData.url);

    } else {
        rawContainer.style.display = 'none';
        rawVipTip.style.display = 'block';
        imgSrcPromise = Promise.resolve(itemData.url); // 普通用户使用原始链接
    }

    imgSrcPromise.then(function (imgSrc) {
        if (!imgSrc) imgSrc = itemData.url;

        // [2] HTML 生成
        // 格式: <a href="{ViewUrl}"><img src="{ImgUrl}"></a>
        document.getElementById('shareLinkHtml').value =
            `<a href="${viewUrl}" target="_blank"><img src="${imgSrc}" alt="${itemData.filename}" border="0"></a>`;

        // [3] Markdown 生成
        // 格式: [![{filename}]({ImgUrl})]({ViewUrl})
        document.getElementById('shareLinkMd').value =
            `[![${itemData.filename}](${imgSrc})](${viewUrl})`;

        // [4] 直链输入框 (仅 VIP 可见)
        if (isVip) {
            document.getElementById('shareLinkRaw').value = imgSrc;
        }
    });

    // Guest 提示
    if (!isLoggedIn) {
        if (mdGuestTip) mdGuestTip.style.display = 'block';
    } else {
        if (mdGuestTip) mdGuestTip.style.display = 'none';
    }


    // 显示模态框
    modal.style.display = 'flex';
};

// 切换折叠
window.toggleCollapse = function (id) {
    var el = document.getElementById(id);
    if (el.style.display === 'none') {
        el.style.display = 'block';
    } else {
        el.style.display = 'none';
    }
};

// 复制输入框内容
window.copyInput = function (id) {
    var input = document.getElementById(id);
    input.select();
    document.execCommand('copy');
    if (window.showToast) window.showToast("复制成功", "success");
};

// 辅助：格式化大小
function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toPrecision(3) + ' ' + sizes[i];
}

// 处理网络图片 (粘贴 URL 或 HTML 图片时调用)
function handleWebImage(url, source) {
    var prefix = source === "paste" ? "paste" : "upload";

    // 1. 重置 UI
    var errorBox = document.getElementById(prefix + "Error");
    var resultBox = document.getElementById(prefix + "Result");
    var loading = document.getElementById(prefix + "Loading");
    var preview = document.getElementById(prefix + "Preview");

    if (errorBox) errorBox.style.display = "none";
    if (resultBox) resultBox.style.display = "none";

    // 显示预览 (直接用 URL)
    if (preview) {
        preview.src = url;
        preview.style.display = "block";
        // 如果图片加载失败，显示错误
        preview.onerror = function () {
            if (window.showError) showError("无法通过链接加载图片，可能是防盗链保护", source);
            this.style.display = "none";
        }
    }

    if (loading) loading.style.display = "block";

    // 2. 后端验证并尝试抓取 (Validate)
    fetch("/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
    })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (loading) loading.style.display = "none";

            if (data.success) {
                // 图片有效，直接显示结果
                // 构造一个类似上传成功的对象
                var resultData = {
                    url: data.url, // 后端可能返回原 URL 或代理 URL
                    service: "网页图片",
                    width: null,
                    height: null,
                    size: null
                };

                // 调用 upload.js 里的显示逻辑
                if (typeof showSuccessResult === 'function') {
                    showSuccessResult(resultData, source);
                }

                // 记录历史
                if (typeof addHistory === 'function') {
                    addHistory({
                        url: data.url,
                        filename: "Web_Image_" + new Date().getTime(),
                        service: "网页图片",
                        uploadType: "网页提取"
                    });
                }

                if (window.showToast) showToast("图片链接提取成功", "success");
            } else {
                if (window.showError) showError("链接无效或不是图片: " + (data.error || ""), source);
            }
        })
        .catch(function (err) {
            if (loading) loading.style.display = "none";
            if (window.showError) showError("网络验证失败", source);
        });
}

// 通用复制函数
function copyToClipboard(text, btnElement) {
    if (!text) return;

    // 创建临时输入框
    var input = document.createElement("textarea");
    input.value = text;
    document.body.appendChild(input);
    input.select();

    try {
        if (typeof btnElement === 'string') {
            // 如果传入的是提示文本而不是按钮元素 (兼容旧代码)
            if (window.showToast) showToast(btnElement, "success");
        } else {
            document.execCommand("copy");
            if (window.showToast) showToast("复制成功!", "success");

            // 按钮视觉反馈
            if (btnElement) {
                var oldText = btnElement.textContent;
                btnElement.textContent = "已复制";
                btnElement.style.background = "var(--success)";
                btnElement.style.color = "white";
                setTimeout(function () {
                    btnElement.textContent = oldText;
                    btnElement.style.background = "";
                    btnElement.style.color = "";
                }, 1500);
            }
        }
    } catch (err) {
        if (window.showToast) showToast("复制失败", "error");
    }

    document.body.removeChild(input);
}
