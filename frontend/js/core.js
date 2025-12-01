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
    } catch (err) {
        if (window.showToast) showToast("复制失败", "error");
    }

    document.body.removeChild(input);
}
