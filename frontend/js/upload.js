// 全局变量：存储本次上传会话的所有结果
window.allUploadResults = []; 
window.uploadPage = 1;
window.uploadPageSize = 5;
// 存储正在上传的任务ID，用于保留进度条
window.activeUploadTasks = [];

document.addEventListener('DOMContentLoaded', function() {
    var dropArea = document.getElementById('uploadArea');
    var fileInput = document.getElementById('fileInput');
    
    // 初始化事件
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

    // --- 分页渲染主逻辑 ---
    window.renderUploadList = function() {
        var listEl = document.getElementById('uploadBatchList');
        var paginationEl = document.getElementById('uploadPagination');

        // 1. 保护正在上传的进度条
        // 因为我们不想因为渲染而导致正在跳动的进度条消失
        // 所以我们只清除非临时卡片
        var tempCards = [];
        window.activeUploadTasks.forEach(function(taskId){
            var el = document.getElementById(taskId);
            if(el) tempCards.push(el); // 把DOM存起来
        });

        // 清空列表
        listEl.innerHTML = '';
        
        // 先放回正在上传的卡片
        tempCards.forEach(function(el) { listEl.appendChild(el); });

        // 2. 检查是否有数据
        var total = window.allUploadResults.length;
        if (total === 0) {
            paginationEl.style.display = 'none';
            return;
        }
        paginationEl.style.display = 'flex';

        // 3. 计算分页
        var totalPages = Math.ceil(total / window.uploadPageSize);
        if (window.uploadPage > totalPages) window.uploadPage = totalPages;
        if (window.uploadPage < 1) window.uploadPage = 1;

        document.getElementById('uploadPageInfo').innerText = window.uploadPage + '/' + totalPages;

        var start = (window.uploadPage - 1) * window.uploadPageSize;
        var end = start + window.uploadPageSize;
        var pageData = window.allUploadResults.slice(start, end);

        // 4. 渲染数据卡片
        pageData.forEach(function(data) {
            var card = createSuccessCard(data);
            listEl.appendChild(card);
        });
    };

    // --- 上传主逻辑 ---
    async function uploadFile(file) {
        var batchList = document.getElementById('uploadBatchList');
        
        // 生成唯一ID
        var taskId = 'upload-task-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        window.activeUploadTasks.push(taskId);

        // 创建临时进度卡片
        var wrapper = document.createElement('div');
        wrapper.id = taskId;
        wrapper.className = 'history-card upload-temp-card'; 
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
            '<div class="progress-bar-container" style="height:3px;background:#eee;margin-top:5px;width:100%">' +
                '<div class="progress-bar" style="height:100%;background:#3b82f6;width:0%;transition:width 0.3s"></div>' +
            '</div>';
        
        // 插入到最前面
        batchList.insertBefore(wrapper, batchList.firstChild);
        
        var bar = wrapper.querySelector('.progress-bar');
        
        try {
            var formData = new FormData();
            formData.append('file', file);
            var nodes = document.querySelectorAll('#uploadServiceSelector input:checked');
            var svcs = [];
            for (var i = 0; i < nodes.length; i++) svcs.push(nodes[i].value);
            formData.append('services', svcs.join(','));

            // 模拟进度
            bar.style.width = '60%';
            
            var resp = await fetch('/upload', { method: 'POST', body: formData });
            var res = await resp.json();
            
            bar.style.width = '100%';

            // 移除临时任务ID
            window.activeUploadTasks = window.activeUploadTasks.filter(function(id){ return id !== taskId; });

            setTimeout(function() {
                wrapper.remove(); // 移除进度条卡片
                
                if (res.success) {
                    // === 核心：前端去重 ===
                    // 如果存在相同 Hash 的图片，先删除旧的，再把新的加到最前
                    var existingIdx = window.allUploadResults.findIndex(function(item) {
                        return item.hash === res.hash;
                    });
                    
                    if (existingIdx !== -1) {
                        window.allUploadResults.splice(existingIdx, 1);
                    }
                    
                    window.allUploadResults.unshift(res);
                    
                    // 同时保存到历史记录
                    if (window.saveToHistory) window.saveToHistory(res);
                    
                } else {
                    // 失败信息也加入列表顶部展示，但不存入数据数组
                    var errCard = createErrorCard(res, file.name);
                    batchList.insertBefore(errCard, batchList.firstChild);
                }
                
                // 刷新列表视图
                window.renderUploadList();

            }, 300);

        } catch (e) {
            console.error(e);
            window.activeUploadTasks = window.activeUploadTasks.filter(function(id){ return id !== taskId; });
            wrapper.querySelector('.source-badge').innerText = '❌ 网络错误';
            wrapper.classList.remove('upload-temp-card'); 
        }
    }

    function createSuccessCard(data) {
        var wrapper = document.createElement('div');
        wrapper.className = 'history-card';
        var all = data.all_results || [{ service: data.service, url: data.url }];
        
        var html = 
        '<div class="history-main-row">' +
            '<img src="' + data.url + '" class="history-thumb">' +
            '<div class="history-info">' +
                '<div class="history-name-row">' +
                    '<span class="history-name" title="'+data.filename+'">' + data.filename + '</span>' +
                    '<span class="source-badge success-badge">' + 
                        (all.length > 1 ? all.length + '个源' : all[0].service) + 
                    '</span>' +
                '</div>';
        
        if (data.failed_list && data.failed_list.length > 0) {
            var msg = [];
            data.failed_list.forEach(function(f){ msg.push(f.service); });
            html += '<div style="color:red;font-size:12px">⚠️ ' + msg.join(',') + ' 失败</div>';
        }

        html += '</div>' + // end info
            '<div class="history-actions">' +
                '<button class="btn-mini" onclick="navigator.clipboard.writeText(\'' + data.url + '\');alert(\'已复制\')">复制</button>' +
                '<button class="btn-mini" onclick="window.open(\'' + data.url + '\')">打开</button>' +
            '</div>' +
        '</div>';

        // 多源下拉列表
        if (all.length > 1) {
            html += '<div class="history-sublist">';
            all.forEach(function(s) {
                html += '<div class="sub-row"><span class="sub-tag">'+s.service+'</span><a href="'+s.url+'" class="sub-link" target="_blank">'+s.url+'</a></div>';
            });
            html += '</div>';
        }

        wrapper.innerHTML = html;
        return wrapper;
    }

    function createErrorCard(res, filename) {
        var wrapper = document.createElement('div');
        wrapper.className = 'history-card error-card';
        wrapper.style.borderColor = '#ef4444';
        wrapper.innerHTML = 
            '<div class="history-main-row">' +
                '<div class="history-info">' +
                    '<span class="history-name">' + filename + '</span>' +
                    '<span class="source-badge">❌ 失败</span>' +
                    '<div style="color:red;font-size:12px;margin-top:4px">' + (res.error || '未知错误') + '</div>' +
                '</div>' +
            '</div>';
        return wrapper;
    }

    // --- 分页控制绑定 ---
    window.nextUploadPage = function() {
        var totalPages = Math.ceil(window.allUploadResults.length / window.uploadPageSize);
        if(window.uploadPage < totalPages) {
            window.uploadPage++;
            window.renderUploadList();
        }
    };
    window.prevUploadPage = function() {
        if(window.uploadPage > 1) {
            window.uploadPage--;
            window.renderUploadList();
        }
    };
    window.changeUploadPageSize = function(val) {
        window.uploadPageSize = parseInt(val);
        window.uploadPage = 1;
        window.renderUploadList();
    };
});
