// 粘贴上传逻辑（仅 MyCloud）

window.lastPasteUrl = null;

// 补全 URL 工具
function getFullUrl(url) {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    if (url.startsWith("/")) return window.location.origin + url;
    return url;
}

// 命名规则 - 优先使用hash
function getDefaultNameFromResultForPaste(res) {
    // 优先使用hash作为文件名
    if (res && res.hash) return res.hash;

    // 如果有filename且不是默认的image.png,使用它
    if (res && res.filename && res.filename !== 'image.png') return res.filename;

    // 最后才从URL解析
    var fullUrl = getFullUrl(res.url);
    if (fullUrl) {
        try {
            var u = new URL(fullUrl);
            var path = u.pathname || "";
            var segs = path.split("/").filter(Boolean);
            if (segs.length) {
                var last = segs[segs.length - 1];
                var dot = last.lastIndexOf(".");
                if (dot > 0) last = last.substring(0, dot);
                if (last) return last;
            }
        } catch (e) { }
    }
    return "img_" + Date.now();
}

document.addEventListener('DOMContentLoaded', function () {
    var pasteArea = document.getElementById('pasteArea');
    var pastePreview = document.getElementById('pastePreview');
    var pasteLoading = document.getElementById('pasteLoading');
    var pasteResultBox = document.getElementById('pasteResult');
    var serviceBadge = document.getElementById('pasteServiceBadge');
    var resultLinkEl = document.getElementById('pasteResultUrl');
    var copyBtn = document.getElementById('pasteCopyBtn');
    // 二维码按钮已删除，不需要获取 qrBtn
    var openBtn = document.getElementById('pasteOpenBtn');
    var infoBox = document.getElementById('pasteImageInfo');

    var nameInput = document.getElementById('pasteFilenameInput');
    var renameBtn = document.getElementById('pasteRenameSaveBtn');

    if (renameBtn && nameInput) {
        renameBtn.onclick = function () {
            var newName = nameInput.value.trim();
            if (!newName) {
                if (window.showToast) window.showToast("名称不能为空", "warning");
                return;
            }
            if (window.lastPasteUrl && window.renameHistoryByUrl) {
                window.renameHistoryByUrl(getFullUrl(window.lastPasteUrl), newName);
                if (window.showToast) window.showToast("名称已更新", "success");
            }
        };
    }

    if (!pasteArea) return;

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

    function looksLikeUrl(text) {
        if (!text) return false;
        return /^https?:\/\//i.test(text.trim());
    }

    function copyText(text) {
        var full = getFullUrl(text);
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(full);
        } else {
            var ta = document.createElement('textarea');
            ta.value = full;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        // 只有 Toast，没有 alert
        if (window.showToast) {
            window.showToast('已复制链接', 'success');
        }
    }

    function renderUploadResult(data) {
        if (!data || !data.url) return;

        var fullUrl = getFullUrl(data.url);
        data.url = fullUrl;
        if (data.all_results) {
            data.all_results.forEach(function (item) { item.url = getFullUrl(item.url); });
        }

        window.lastPasteUrl = fullUrl;

        var displayName = getDefaultNameFromResultForPaste(data);
        data.filename = displayName;

        setPreview(fullUrl);
        if (serviceBadge) serviceBadge.style.display = 'none'; // 隐藏服务标签
        if (resultLinkEl) {
            resultLinkEl.textContent = fullUrl;
            resultLinkEl.href = fullUrl;
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

        if (nameInput) {
            nameInput.value = displayName;
        }

        showResultBox(true);

        // 刷新历史记录 (如果已加载)
        if (typeof window.displayHistory === 'function') {
            window.displayHistory();
        }
    }

    async function handleImageFilePaste(file) {
        if (!file) return;
        showLoading(true);
        showResultBox(false);

        var localUrl = URL.createObjectURL(file);
        setPreview(localUrl);

        try {
            var form = new FormData();
            form.append('file', file);
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            var data = await resp.json();
            showLoading(false);

            if (!data.success) {
                if (window.showToast) window.showToast('链接不可用', 'error');
                else alert('链接不可用');
                return;
            }

            window.lastPasteUrl = url;

            var fakeRes = { url: url, service: '网页图片' };
            var displayName = getDefaultNameFromResultForPaste(fakeRes);
            fakeRes.filename = displayName;

            setPreview(url);
            if (serviceBadge) serviceBadge.style.display = 'none'; // 隐藏服务标签
            if (resultLinkEl) {
                resultLinkEl.textContent = url;
                resultLinkEl.href = url;
            }
            if (infoBox) infoBox.innerHTML = '';
            if (nameInput) nameInput.value = displayName;
            showResultBox(true);

            if (window.saveToHistory) {
                window.saveToHistory({
                    url: url,
                    service: '网页图片',
                    filename: displayName,
                    hash: null,
                    all_results: [{ service: '网页图片', url: url }]
                });
            }

        } catch (e) {
            showLoading(false);
            console.error(e);
            if (window.showToast) window.showToast('验证失败', 'error');
            else alert('验证失败');
        }
    }

    function onPaste(e) {
        var clipboard = e.clipboardData || window.clipboardData;
        if (!clipboard) return;

        var items = clipboard.items;
        if (items && items.length) {
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

        var text = clipboard.getData('text');
        if (text && looksLikeUrl(text)) {
            e.preventDefault();
            handleUrlPaste(text);
        }
    }

    pasteArea.addEventListener('paste', onPaste);
    window.addEventListener('paste', function (e) {
        var active = document.activeElement;
        var tag = active && active.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        onPaste(e);
    });

    pasteArea.addEventListener('click', function () {
        pasteArea.focus();
    });

    if (copyBtn) {
        copyBtn.addEventListener('click', function () {
            if (resultLinkEl.textContent) {
                copyText(resultLinkEl.textContent);
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
});
