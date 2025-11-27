// upload.js - 完整版，包含前端分页、去重

// 全局状态
window.allUploadResults = []; 
window.uploadPage = 1;
window.uploadPageSize = 10;

document.addEventListener('DOMContentLoaded', function() {
    var dropArea = document.getElementById('uploadArea');
    var fileInput = document.getElementById('fileInput');

    // 初始化拖拽和选择事件
    if (dropArea) {
        dropArea.onclick = function() { fileInput.click(); };
        dropArea.ondragover = function(e) { e.preventDefault(); this.classList.add('drag-over'); };
        dropArea.ondragleave = function() { this.classList.remove('drag-over'); };
        dropArea.ondrop = function(e) { e.preventDefault(); this.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); };
    }
    if (fileInput) fileInput.onchange = function(e) { handleFiles(e.target.files); };

    function handleFiles(files) {
        if (!files.length) return;
        // 转为数组处理
        var arr = [];
        for(var i=0; i<files.length; i++) arr.push(files[i]);
        arr.forEach(uploadFile);
        fileInput.value = ''; 
    }

    // === 分页渲染器 ===
    window.renderUploadList = function() {
        var listEl = document.getElementById('uploadBatchList');
        var pagi = document.getElementById('uploadPagination');
        
        // 1. 保护进度条：把正在上传的临时卡片拿出来
        var temps = [];
        var children = listEl.children;
        for(var i=0; i<children.length; i++) {
            if(children[i].classList.contains('temp-card')) temps.push(children[i]);
        }
        
        listEl.innerHTML = '';
        
        // 2. 先放进度条
        temps.forEach(function(node) { listEl.appendChild(node); });

        // 3. 检查数据量
        var total = window.allUploadResults.length;
        if (total === 0 && temps.length === 0) {
            if(pagi) pagi.style.display = 'none';
            return;
        }
        if(pagi) pagi.style.display = 'flex';

        // 4. 计算分页
        var maxPage = Math.ceil(total / window.uploadPageSize);
        if (maxPage < 1) maxPage = 1;
        if (window.uploadPage > maxPage) window.uploadPage = maxPage;
        if (window.uploadPage < 1) window.uploadPage = 1;

        // 更新页码显示
        var info = document.getElementById('uploadPageInfo');
        if(info) info.innerText = window.uploadPage + ' / ' + maxPage;

        // 5. 切片并渲染
        var start = (window.uploadPage - 1) * window.uploadPageSize;
        var end = start + window.uploadPageSize;
        var slice = window.allUploadResults.slice(start, end);

        slice.forEach(function(data) {
            listEl.appendChild(createResultCard(data));
        });
    };

    // === 上传逻辑 ===
    async function uploadFile(file) {
        var batchList = document.getElementById('uploadBatchList');
        
        // 创建临时卡片
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
            for(var i=0; i<nodes.length; i++) svcs.push(nodes[i].value);
            formData.append('services', svcs.join(','));

            bar.style.width = '50%';
            var resp = await fetch('/upload', { method: 'POST', body: formData });
            var res = await resp.json();
            bar.style.width = '100%';

            setTimeout(function() {
                // 移除临时卡片
                if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);

                if (res.success) {
                    // === 核心去重 ===
                    // 如果 hash 相同，删除数组里旧的
                    var oldIdx = -1;
                    for(var k=0; k<window.allUploadResults.length; k++) {
                        if (window.allUploadResults[k].hash === res.hash) {
                            oldIdx = k;
                            break;
                        }
                    }
                    if (oldIdx !== -1) window.allUploadResults.splice(oldIdx, 1);
                    
                    // 加到最前
                    window.allUploadResults.unshift(res);
                    
                    // 保存历史
                    if (window.saveToHistory) window.saveToHistory(res);
                } else {
                    // 失败卡片直接插 DOM，不进数组
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
        
        var html = 
            '<div class="history-main-row">' +
                '<img src="' + data.url + '" class="history-thumb">' +
                '<div class="history-info">' +
                    '<div class="history-name-row">' +
                        '<span class="history-name">' + data.filename + '</span>' +
                        '<span class="source-badge" style="color:green;background:#ecfdf5">' + 
                           (all.length > 1 ? all.length+'个源' : data.service) + 
                        '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="history-actions">' +
                    '<button class="btn-mini" onclick="navigator.clipboard.writeText(\''+data.url+'\');alert(\'已复制\')">复制</button>' +
                    '<button class="btn-mini" onclick="window.open(\''+data.url+'\')">打开</button>' +
                '</div>' +
            '</div>';
        
        if (all.length > 1) {
            html += '<div class="history-sublist">';
            all.forEach(function(s){
                 html += '<div class="sub-row"><span class="sub-tag">'+s.service+'</span><a href="'+s.url+'" class="sub-link" target="_blank">'+s.url+'</a></div>';
            });
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
                    '<div style="color:red;font-size:12px;margin-top:5px">上传失败: ' + (res.error||'未知') + '</div>' +
                '</div>' +
            '</div>';
        return div;
    }

    // 暴露的控制方法
    window.prevUploadPage = function() { 
        if(window.uploadPage > 1) { window.uploadPage--; window.renderUploadList(); }
    };
    window.nextUploadPage = function() { 
        var max = Math.ceil(window.allUploadResults.length / window.uploadPageSize);
        if(window.uploadPage < max) { window.uploadPage++; window.renderUploadList(); }
    };
    window.changeUploadPageSize = function(v) { 
        window.uploadPageSize = parseInt(v); 
        window.uploadPage = 1; 
        window.renderUploadList(); 
    };
});
