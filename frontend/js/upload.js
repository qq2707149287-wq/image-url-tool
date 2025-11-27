// upload.js - 批量上传 + 分页 + 去重 + 重命名最新上传

window.allUploadResults = [];
window.uploadPage = 1;
window.uploadPageSize = 10;
window.lastUploadResultUrl = null;

// 统一命名规则：
// 1. 有 hash 就用 hash
// 2. 否则从 URL 里取最后一段（去掉后缀）
// 3. 都没有就用时间戳
function getDefaultNameFromResult(res) {
    if (res && res.hash) {
        return res.hash;
    }
    var url = res && res.url ? res.url : "";
    if (url) {
        try {
            var u = new URL(url, window.location.origin);
            var path = u.pathname || "";
            var segs = path.split("/").filter(Boolean);
            if (segs.length) {
                var last = segs[segs.length - 1]; // xxx.png
                var dot = last.lastIndexOf(".");
                if (dot > 0) last = last.substring(0, dot);
                if (last) return last;
            }
        } catch (e) {
            // 忽略解析错误
        }
    }
    return "img_" + Date.now();
}

document.addEventListener('DOMContentLoaded', function() {
    var dropArea = document.getElementById('uploadArea');
    var fileInput = document.getElementById('fileInput');

    var uploadNameInput = document.getElementById('uploadFilenameInput');
    var uploadRenameBtn = document.getElementById('uploadRenameSaveBtn');

    if (uploadRenameBtn && uploadNameInput) {
        uploadRenameBtn.onclick = function () {
            var newName = uploadNameInput.value.trim();
            if (!newName) {
                alert("名称不能为空");
                return;
            }
            if (window.lastUploadResultUrl && window.renameHistoryByUrl) {
                window.renameHistoryByUrl(window.lastUploadResultUrl, newName);
                if (window.showToast) window.showToast("名称已更新");
            }
        };
    }

    if (dropArea) {
        dropArea.onclick = function() { fileInput.click(); };
        dropArea.ondragover = function(e) { e.preventDefault(); this.classList.add('drag-over'); };
        dropArea.ondragleave = function() { this.classList.remove('drag-over'); };
        dropArea.ondrop = function(e) { e.preventDefault(); this.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); };
    }
    if (fileInput) fileInput.onchange = function(e) { handleFiles(e.target.files); };

    function handleFiles(files) {
        if (!files.length) return;
        var arr = [];
        for (var i = 0; i < files.length; i++) arr.push(files[i]);
        arr.forEach(uploadFile);
        fileInput.value = ''; 
    }

    window.renderUploadList = function() {
        var listEl = document.getElementById('uploadBatchList');
        var pagi = document.getElementById('uploadPagination');
        
        var temps = [];
        var children = listEl.children;
        for (var i = 0; i < children.length; i++) {
            if (children[i].classList.contains('temp-card')) temps.push(children[i]);
        }
        
        listEl.innerHTML = '';
        for (var j = 0; j < temps.length; j++) listEl.appendChild(temps[j]);

        var total = window.allUploadResults.length;
        if (total === 0 && temps.length === 0) {
            if (pagi) pagi.style.display = 'none';
            return;
        }
        if (pagi) pagi.style.display = 'flex';

        var maxPage = Math.ceil(total / window.uploadPageSize);
        if (maxPage < 1) maxPage = 1;
        if (window.uploadPage > maxPage) window.uploadPage = maxPage;
        if (window.uploadPage < 1) window.uploadPage = 1;

        var info = document.getElementById('uploadPageInfo');
        if (info) info.innerText = window.uploadPage + ' / ' + maxPage;

        var start = (window.uploadPage - 1) * window.uploadPageSize;
        var end = start + window.uploadPageSize;
        var slice = window.allUploadResults.slice(start, end);

        slice.forEach(function(data) {
            listEl.appendChild(createResultCard(data));
        });
    };

    async function uploadFile(file) {
        var batchList = document.getElementById('uploadBatchList');
        
        var wrapper = document.createElement('div');
        wrapper.className = 'history-card temp-card';
        wrapper.style.opacity = '0.8';
        
        var url = URL.createObjectURL(file);
        wrapper.innerHTML = 
            '<div class="history-main-row">' +
                '<img src="' + url + '" class="history-thumb">' +
                '<div class="history-info">' +
                    '<span class="history-name">' + file.name + '</span>' +
                    '<span class="source-badge">⏳ 上传中...</span>' +
                '</div>' +
            '</div>' +
            '<div class="batch-progress-bar" style="width:0%"></div>';
        
        batchList.insertBefore(wrapper, batchList.firstChild);
        var bar = wrapper.querySelector('.batch-progress-bar');
        
        try {
            var formData = new FormData();
            formData.append('file', file);
            var nodes = document.querySelectorAll('#uploadServiceSelector input:checked');
            var svcs = [];
            for (var i = 0; i < nodes.length; i++) svcs.push(nodes[i].value);
            if (svcs.length === 0) svcs.push('myminio');
            formData.append('services', svcs.join(','));

            bar.style.width = '50%';
            var resp = await fetch('/upload', { method: 'POST', body: formData });
            var res = await resp.json();
            bar.style.width = '100%';

            setTimeout(function() {
                if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);

                if (res.success) {
                    var oldIdx = -1;
                    for (var k = 0; k < window.allUploadResults.length; k++) {
                        if (window.allUploadResults[k].hash === res.hash) {
                            oldIdx = k;
                            break;
                        }
                    }
                    if (oldIdx !== -1) window.allUploadResults.splice(oldIdx, 1);
                    
                    // 生成默认显示名称（hash / URL 里的长串）
                    var displayName = getDefaultNameFromResult(res);
                    res.filename = displayName;

                    window.allUploadResults.unshift(res);

                    window.lastUploadResultUrl = res.url;

                    if (uploadNameInput) {
                        uploadNameInput.value = displayName;
                    }

                    if (window.saveToHistory) window.saveToHistory(res);
                } else {
                    var err = createErrorCard(res, file.name);
                    batchList.insertBefore(err, batchList.firstChild);
                }
                
                window.renderUploadList();
            }, 400);

        } catch (e) {
            console.error(e);
            if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
        }
    }

    function createResultCard(data) {
        var div = document.createElement('div');
        div.className = 'history-card';
        var all = data.all_results || [{ service: data.service, url: data.url }];
        
        var name = getDefaultNameFromResult(data);

        var html = 
            '<div class="history-main-row">' +
                '<img src="' + data.url + '" class="history-thumb">' +
                '<div class="history-info">' +
                    '<div class="history-name-row">' +
                        '<span class="history-name">' + name + '</span>' +
                        '<span class="source-badge" style="color:green;background:#ecfdf5">' + 
                           (all.length > 1 ? all.length + '个源' : (data.service || "MyCloud")) + 
                        '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="history-actions">' +
                    '<button class="btn-mini" onclick="navigator.clipboard.writeText(\'' + data.url + '\');alert(\'已复制\')">复制</button>' +
                    '<button class="btn-mini" onclick="window.open(\'' + data.url + '\')">打开</button>' +
                '</div>' +
            '</div>';
        
        if (all.length > 1) {
            html += '<div class="history-sublist">';
            for (var i = 0; i < all.length; i++) {
                var s = all[i];
                html += '<div class="sub-row"><span class="sub-tag">' + s.service + '</span><a href="' + s.url + '" class="sub-link" target="_blank">' + s.url + '</a></div>';
            }
            html += '</div>';
        }
        div.innerHTML = html;
        return div;
    }

    function createErrorCard(res, fname) {
        var div = document.createElement('div');
        div.className = 'history-card';
        div.style.borderColor = 'red';
        div.innerHTML = 
            '<div class="history-main-row">' +
                '<div class="history-info">' +
                    '<span class="history-name">' + fname + '</span>' +
                    '<div style="color:red;font-size:12px;margin-top:5px">上传失败: ' + (res.error || '未知') + '</div>' +
                '</div>' +
            '</div>';
        return div;
    }

    window.prevUploadPage = function() { 
        if (window.uploadPage > 1) { window.uploadPage--; window.renderUploadList(); }
    };
    window.nextUploadPage = function() { 
        var max = Math.ceil(window.allUploadResults.length / window.uploadPageSize);
        if (window.uploadPage < max) { window.uploadPage++; window.renderUploadList(); }
    };
    window.changeUploadPageSize = function(v) { 
        window.uploadPageSize = parseInt(v, 10); 
        window.uploadPage = 1; 
        window.renderUploadList(); 
    };
});
