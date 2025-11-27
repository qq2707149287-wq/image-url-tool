// 历史记录JS - 支持分页
window.historyPage = 1;
window.historyPageSize = 5; // 默认每页5条
window.historyData = []; // 内存中缓存此数据

document.addEventListener('DOMContentLoaded', function() {
    loadHistory();
});

// 保存到历史 (带去重)
window.saveToHistory = function(data) {
    // 从 localStorage 读取
    var raw = localStorage.getItem('imgHistory');
    var history = raw ? JSON.parse(raw) : [];
    
    // 去重 logic: 优先检查 hash，没有hash检查url
    var idx = -1;
    if (data.hash) {
        idx = history.findIndex(function(i) { return i.hash === data.hash; });
    } else {
        idx = history.findIndex(function(i) { return i.url === data.url; });
    }

    // 如果已存在，删除旧的
    if (idx !== -1) {
        history.splice(idx, 1); 
    }

    // 构建新对象
    var item = {
        url: data.url,
        filename: data.filename,
        service: data.service,
        hash: data.hash,
        time: new Date().getTime(),
        width: data.width || 0,
        height: data.height || 0,
        size: data.size || 0,
        all_results: data.all_results
    };

    // 加到最前面
    history.unshift(item); 
    
    // 限制最大条数保护浏览器内存
    if (history.length > 200) history.pop(); 

    localStorage.setItem('imgHistory', JSON.stringify(history));
    
    // 刷新显示
    loadHistory(); 
};

// 加载并渲染历史
window.loadHistory = function() {
    var raw = localStorage.getItem('imgHistory');
    window.historyData = raw ? JSON.parse(raw) : [];
    
    // 搜索过滤
    var search = document.getElementById('searchInput');
    if (search && search.value) {
        var term = search.value.toLowerCase();
        window.historyData = window.historyData.filter(function(item) {
            var n = item.filename || '';
            var u = item.url || '';
            return n.toLowerCase().includes(term) || u.toLowerCase().includes(term);
        });
    }

    renderHistoryPage();
};

window.renderHistoryPage = function() {
    var list = document.getElementById('historyList');
    var pagi = document.getElementById('historyPagination');
    list.innerHTML = '';

    var total = window.historyData.length;
    if (total === 0) {
        list.innerHTML = '<div style="text-align:center;color:#999;padding:40px">暂无记录</div>';
        pagi.style.display = 'none';
        return;
    }
    pagi.style.display = 'flex';

    var totalPages = Math.ceil(total / window.historyPageSize);
    if (window.historyPage > totalPages) window.historyPage = totalPages;
    if (window.historyPage < 1) window.historyPage = 1;

    document.getElementById('historyPageInfo').innerText = window.historyPage + '/' + totalPages;

    var start = (window.historyPage - 1) * window.historyPageSize;
    var end = start + window.historyPageSize;
    var pageItems = window.historyData.slice(start, end);

    pageItems.forEach(function(item) {
        var div = document.createElement('div');
        div.className = 'history-card';
        
        var html = 
            '<div class="history-main-row">' +
                '<img src="' + item.url + '" class="history-thumb" onerror="this.style.display=\'none\'">' +
                '<div class="history-info">' +
                    '<div class="history-name-row">' +
                        '<span class="history-name" title="' + item.filename + '">' + (item.filename || '未命名') + '</span>' +
                        '<span class="source-badge">' + item.service + '</span>' +
                    '</div>' +
                    '<div style="font-size:12px;color:#999;margin-top:4px">' + 
                        new Date(item.time).toLocaleString() + 
                    '</div>' +
                '</div>' +
                '<div class="history-actions">' +
                    '<button class="btn-mini" onclick="copyUrl(\'' + item.url + '\')">复制</button>' +
                    '<button class="btn-mini" onclick="window.open(\'' + item.url + '\')">打开</button>' +
                '</div>' +
            '</div>';
        
        div.innerHTML = html;
        list.appendChild(div);
    });
};

// 导出功能 - 修复 Blob 问题
window.exportHistory = function() {
    var data = localStorage.getItem('imgHistory');
    if (!data) {
        alert('没有记录可导出');
        return;
    }
    
    // 使用更兼容的方式创建 Blob
    try {
        var blobParts = [data];
        var options = { type: 'application/json' };
        var blob = new Blob(blobParts, options);
        
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'image_history_backup_' + new Date().toISOString().slice(0,10) + '.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('导出失败', e);
        alert('浏览器不支持文件导出，请手动复制 localStorage 中的内容');
    }
};

window.importHistory = function(input) {
    var file = input.files[0];
    if (!file) return;
    
    var reader = new FileReader();
    reader.onload = function(e) {
        try {
            var imported = JSON.parse(e.target.result);
            if (Array.isArray(imported)) {
                // 合并现有记录
                var current = JSON.parse(localStorage.getItem('imgHistory') || '[]');
                
                // 简单的合并去重
                imported.forEach(function(newItem) {
                    var exists = current.some(function(oldItem) { 
                        return oldItem.url === newItem.url; 
                    });
                    if (!exists) current.push(newItem);
                });
                
                // 按时间倒序排序
                current.sort(function(a, b) { return b.time - a.time; });
                
                localStorage.setItem('imgHistory', JSON.stringify(current));
                loadHistory();
                alert('导入成功，新增记录已合并');
            } else {
                alert('文件格式错误');
            }
        } catch (err) {
            alert('文件解析失败');
        }
    };
    reader.readAsText(file);
    input.value = ''; // 重置
};

// 分页与清理操作
window.filterHistory = function() { window.historyPage = 1; loadHistory(); };
window.clearHistory = function() {
    if(confirm('确定清空所有历史记录吗？')) {
        localStorage.removeItem('imgHistory');
        loadHistory();
    }
};
window.nextHistoryPage = function() {
    var totalPages = Math.ceil(window.historyData.length / window.historyPageSize);
    if(window.historyPage < totalPages) { window.historyPage++; renderHistoryPage(); }
};
window.prevHistoryPage = function() {
    if(window.historyPage > 1) { window.historyPage--; renderHistoryPage(); }
};
window.changeHistoryPageSize = function(val) {
    window.historyPageSize = parseInt(val);
    window.historyPage = 1;
    renderHistoryPage();
};

// 辅助复制函数
window.copyUrl = function(url) {
    navigator.clipboard.writeText(url).then(function() {
        alert('已复制');
    }, function() {
        alert('复制失败，请手动复制');
    });
};
