document.addEventListener('DOMContentLoaded', function() {
    var dropArea = document.getElementById('uploadArea');
    var fileInput = document.getElementById('fileInput');
    
    // 初始化事件绑定
    if (dropArea) {
        dropArea.onclick = function() { fileInput.click(); };
        dropArea.ondragover = function(e) { e.preventDefault(); this.classList.add('drag-over'); };
        dropArea.ondragleave = function() { this.classList.remove('drag-over'); };
        dropArea.ondrop = function(e) { e.preventDefault(); this.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); };
    }
    if (fileInput) fileInput.onchange = function(e) { handleFiles(e.target.files); };

    function handleFiles(files) {
        if (!files.length) return;
        Array.from(files).forEach(uploadFile);
        fileInput.value = '';
    }
    async function uploadFile(file) {
        var batchList = document.getElementById('uploadBatchList');
        var wrapper = document.createElement('div');
        wrapper.className = 'history-card';
        wrapper.style.opacity = '0.7';

        // 缩略图预览
        var url = URL.createObjectURL(file);
        
        wrapper.innerHTML = 
            '<div class="history-main-row">' +
                '<img src="' + url + '" class="history-thumb">' +
                '<div class="history-info">' +
                    '<span class="history-name">' + file.name + '</span>' +
                    '<span class="source-badge">⏳ 上传中...</span>' +
                '</div>' +
            '</div>' +
            '<div class="progress-bar" style="height:2px;background:blue;width:0%"></div>';
        
        batchList.insertBefore(wrapper, batchList.firstChild);
        var bar = wrapper.querySelector('.progress-bar');
        
        try {
            var formData = new FormData();
            formData.append('file', file);
            
            // 获取图床选项
            var nodes = document.querySelectorAll('#uploadServiceSelector input:checked');
            var svcs = [];
            for (var i = 0; i < nodes.length; i++) svcs.push(nodes[i].value);
            formData.append('services', svcs.join(','));

            bar.style.width = '50%';
            
            var resp = await fetch('/upload', { method: 'POST', body: formData });
            var res = await resp.json();
            
            bar.style.width = '100%';
            setTimeout(function() { bar.remove(); wrapper.style.opacity = '1'; }, 300);

            if (res.success) {
                // 成功：渲染成功卡片
                renderSuccessCard(wrapper, res);
                if (window.saveToHistory) window.saveToHistory(res);
            } else {
                // 失败：渲染失败提示
                renderErrorCard(wrapper, res);
            }
        } catch (e) {
            console.error(e);
            wrapper.querySelector('.source-badge').innerText = '❌ 失败';
            wrapper.style.border = '1px solid red';
        }
    }
    function renderSuccessCard(wrapper, data) {
        var all = data.all_results || [{ service: data.service, url: data.url }];
        var info = wrapper.querySelector('.history-info');
        
        // 清空旧内容，重新构建
        info.innerHTML = ''; 
        
        var row = document.createElement('div');
        row.className = 'history-name-row';
        row.innerHTML = '<span class="history-name">' + data.filename + '</span>';
        
        var badge = document.createElement('span');
        badge.className = 'source-badge';
        badge.innerText = all.length > 1 ? all.length + '个源' : data.service;
        badge.style.color = '#22c55e';
        badge.style.background = '#ecfdf5';
        row.appendChild(badge);
        info.appendChild(row);

        // 如果有部分失败，显示红字
        if (data.failed_list && data.failed_list.length > 0) {
            var errDiv = document.createElement('div');
            errDiv.style.color = 'red';
            errDiv.style.fontSize = '12px';
            var msg = [];
            data.failed_list.forEach(function(f){ msg.push(f.service + ': ' + f.error); });
            errDiv.innerText = '⚠️ ' + msg.join(', ');
            info.appendChild(errDiv);
        }

        // 按钮组
        var actions = document.createElement('div');
        actions.className = 'history-actions';
        
        var btnC = document.createElement('button');
        btnC.className = 'btn-mini';
        btnC.innerText = '复制';
        btnC.onclick = function() { navigator.clipboard.writeText(data.url); alert("已复制"); };
        
        var btnO = document.createElement('button');
        btnO.className = 'btn-mini';
        btnO.innerText = '打开';
        btnO.onclick = function() { window.open(data.url); };
        
        actions.appendChild(btnC);
        actions.appendChild(btnO);
        
        wrapper.querySelector('.history-main-row').appendChild(actions);

        // 子列表
        if (all.length > 1) {
            var sub = document.createElement('div');
            sub.className = 'history-sublist';
            all.forEach(function(s) {
                var r = document.createElement('div');
                r.className = 'sub-row';
                r.innerHTML = '<span class="sub-tag">'+s.service+'</span><a href="'+s.url+'" class="sub-link" target="_blank">'+s.url+'</a>';
                sub.appendChild(r);
            });
            wrapper.appendChild(sub);
        }
    }

    function renderErrorCard(wrapper, res) {
        var b = wrapper.querySelector('.source-badge');
        b.innerText = '全部失败';
        b.style.color = 'red';
        
        var errInfo = document.createElement('div');
        errInfo.style.padding = '10px';
        errInfo.style.color = 'red';
        errInfo.style.fontSize = '12px';
        
        if (res.failed_list) {
            res.failed_list.forEach(function(f) {
                var p = document.createElement('div');
                p.innerText = '❌ ' + f.service + ': ' + f.error;
                errInfo.appendChild(p);
            });
        } else {
            errInfo.innerText = res.error || '未知错误';
        }
        wrapper.appendChild(errInfo);
    }
});
