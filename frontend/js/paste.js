// 粘贴上传逻辑（仅使用 MyCloud）

document.addEventListener('DOMContentLoaded', function () {
    var pasteArea       = document.getElementById('pasteArea');
    var pastePreview    = document.getElementById('pastePreview');
    var pasteLoading    = document.getElementById('pasteLoading');
    var pasteResultBox  = document.getElementById('pasteResult');
    var serviceBadge    = document.getElementById('pasteServiceBadge');
    var resultLinkEl    = document.getElementById('pasteResultUrl');
    var copyBtn         = document.getElementById('pasteCopyBtn');
    var qrBtn           = document.getElementById('pasteQrBtn');
    var openBtn         = document.getElementById('pasteOpenBtn');
    var infoBox         = document.getElementById('pasteImageInfo');

    if (!pasteArea) return; // 安全保护

    function showLoading(show) {
        if (pasteLoading) pasteLoading.style.display = show ? 'flex' : 'none';
    }

    function showResultBox(show) {
        if (pasteResultBox) pasteResultBox.style.display = show ? 'block' : 'none';
    }

    function setPreview(src) {
        if (pastePreview) {
            pastePreview.src = src;
            pastePreview.style.display = 'block';
        }
    }

    // 简单的 URL 判断
    function looksLikeUrl(text) {
        if (!text) return false;
        return /^https?:\/\//i.test(text.trim());
    }

    // 复制：这里直接复制 URL（不折腾格式）
    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text);
        } else {
            var ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        if (window.showToast) {
            window.showToast('已复制链接');
        } else {
            alert('已复制链接');
        }
    }

    // 把上传结果渲染到粘贴结果框 + 写入历史
    function renderUploadResult(data) {
        if (!data || !data.url) return;
        var url = data.url;

        setPreview(url);
        if (serviceBadge) serviceBadge.textContent = data.service || 'MyCloud';
        if (resultLinkEl) {
            resultLinkEl.textContent = url;
            resultLinkEl.href = url;
        }

        if (infoBox) {
            infoBox.innerHTML = '';
            var arr = [];
            if (data.width && data.height) {
                arr.push('尺寸: ' + data.width + ' x ' + data.height);
            }
            if (data.size) {
                var kb = (data.size / 1024).toFixed(1);
                arr.push('大小: ' + kb + ' KB');
            }
            if (arr.length) {
                var p = document.createElement('p');
                p.textContent = arr.join('  |  ');
                infoBox.appendChild(p);
            }
        }

        showResultBox(true);

        // 同时写入历史
        if (window.saveToHistory) {
            window.saveToHistory({
                url: url,
                service: data.service || 'MyCloud',
                filename: data.filename || '粘贴上传',
                hash: data.hash || null,
                all_results: data.all_results || [{
                    service: data.service || 'MyCloud',
                    url: url
                }],
                width: data.width,
                height: data.height,
                size: data.size
            });
        }
    }

    // 处理图片文件粘贴
    async function handleImageFilePaste(file) {
        if (!file) return;
        showLoading(true);
        showResultBox(false);

        // 预览本地图
        var localUrl = URL.createObjectURL(file);
        setPreview(localUrl);

        try {
            var form = new FormData();
            form.append('file', file);
            // 后端现在只认 myminio，但这个字段保留也无妨
            form.append('services', 'myminio');

            var resp = await fetch('/upload', {
                method: 'POST',
                body: form
            });
            var data = await resp.json();
            showLoading(false);

            if (!data.success) {
                var msg = data.error || '上传失败';
                if (window.showToast) window.showToast(msg, 'error');
                else alert(msg);
                return;
            }
            renderUploadResult(data);
        } catch (e) {
            showLoading(false);
            console.error(e);
            if (window.showToast) window.showToast('网络错误', 'error');
            else alert('网络错误');
        }
    }

    // 处理文本 URL 粘贴（当网页图片用）
    async function handleUrlPaste(url) {
        url = url.trim();
        if (!looksLikeUrl(url)) {
            if (window.showToast) window.showToast('粘贴内容不是有效链接', 'error');
            else alert('粘贴内容不是有效链接');
            return;
        }
        showLoading(true);
        showResultBox(false);

        try {
            var resp = await fetch('/validate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            });
            var data = await resp.json();
            showLoading(false);

            if (!data.success) {
                if (window.showToast) window.showToast('链接不可用', 'error');
                else alert('链接不可用');
                return;
            }

            // 预览直接用原链接
            setPreview(url);
            if (serviceBadge) serviceBadge.textContent = '网页图片';
            if (resultLinkEl) {
                resultLinkEl.textContent = url;
                resultLinkEl.href = url;
            }
            if (infoBox) infoBox.innerHTML = '';
            showResultBox(true);

            // 也写入历史（类型：网页图片）
            if (window.saveToHistory) {
                window.saveToHistory({
                    url: url,
                    service: '网页图片',
                    filename: '粘贴链接',
                    hash: null,
                    all_results: [{service: '网页图片', url: url}]
                });
            }

        } catch (e) {
            showLoading(false);
            console.error(e);
            if (window.showToast) window.showToast('验证失败', 'error');
            else alert('验证失败');
        }
    }

    // 主 paste 事件处理
    function onPaste(e) {
        var clipboard = e.clipboardData || window.clipboardData;
        if (!clipboard) return;

        var items = clipboard.items;
        if (items && items.length) {
            // 先找图片文件
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (it.kind === 'file' && it.type.indexOf('image/') === 0) {
                    var file = it.getAsFile();
                    e.preventDefault();
                    handleImageFilePaste(file);
                    return;
                }
            }
        }

        // 退而求其次：尝试当文本 URL
        var text = clipboard.getData('text');
        if (text && looksLikeUrl(text)) {
            e.preventDefault();
            handleUrlPaste(text);
        }
    }

    // 既绑定 paste 区域，也绑定全局，防止用户忘记点一下区域
    pasteArea.addEventListener('paste', onPaste);
    window.addEventListener('paste', function (e) {
        // 如果当前 focus 在输入框里，你可能是在别的地方粘贴，就忽略
        var active = document.activeElement;
        var tag = active && active.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        onPaste(e);
    });

    // 区域点击时获取焦点，提示用户
    pasteArea.addEventListener('click', function () {
        pasteArea.focus();
    });

    // 绑定三个按钮
    if (copyBtn) {
        copyBtn.addEventListener('click', function () {
            if (resultLinkEl && resultLinkEl.href) {
                copyText(resultLinkEl.href);
            }
        });
    }
    if (openBtn) {
        openBtn.addEventListener('click', function () {
            if (resultLinkEl && resultLinkEl.href) {
                window.open(resultLinkEl.href, '_blank');
            }
        });
    }
    if (qrBtn) {
        qrBtn.addEventListener('click', function () {
            if (resultLinkEl && resultLinkEl.href && window.showQrForUrl) {
                window.showQrForUrl(resultLinkEl.href, '粘贴图片');
            }
        });
    }
});
