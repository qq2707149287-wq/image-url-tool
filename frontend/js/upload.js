// upload.js - 批量上传 + 多选 + 缩略图修复 + 说明文件生成

window.allUploadResults = [];
window.uploadPage = 1;
window.uploadPageSize = 10;
window.lastUploadResultUrl = null;
window.uploadSelectedHashes = new Set(); // 存储上传列表中被选中的项目 (用 hash 做 key)

// 工具: 补全URL
function getFullUrl(url) {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    if (url.startsWith("/")) return window.location.origin + url;
    return url;
}

// 工具: 默认命名
function getDefaultNameFromResult(res) {
    if (res && res.filename) return res.filename;
    if (res && res.hash) return res.hash;
    return "img_" + Date.now();
}

// 工具: 数据清洗 (用于生成说明文件)
function cleanUploadDataForExport(dataList) {
    var result = [];
    for (var i = 0; i < dataList.length; i++) {
        var item = dataList[i];
        var cleanItem = {};

        if (item.url) cleanItem.url = getFullUrl(item.url);
        if (item.filename) cleanItem.filename = item.filename;

        // 添加带单位的文件大小
        if (item.size) {
            var sizeInKB = (item.size / 1024).toFixed(2);
            cleanItem.size = sizeInKB + ' KB';
        }

        if (item.content_type) {
            cleanItem.content_type = item.content_type;
        }

        result.push(cleanItem);
    }
    return result;
}

document.addEventListener('DOMContentLoaded', function () {
    // DOM 引用
    var dropArea = document.getElementById('uploadArea');
    var fileInput = document.getElementById('fileInput');
    var uploadNameInput = document.getElementById('uploadFilenameInput');


    // 多选相关 DOM
    var toolbar = document.getElementById('uploadMultiToolbar');
    var selectAll = document.getElementById('uploadSelectAll');
    var selectedCount = document.getElementById('uploadSelectedCount');
    var batchDelBtn = document.getElementById('uploadBatchDelBtn');
    var batchGenBtn = document.getElementById('uploadBatchGenBtn');
    // var copyAllBtn = document.getElementById('copyAllCurrentBtn'); // Removed

    // 结果展示区域
    var descModal = document.getElementById("descModal");
    var descTextarea = document.getElementById("descTextarea");

    // 2. 拖拽和文件选择
    if (dropArea) {
        dropArea.onclick = function () { fileInput.click(); };
        dropArea.ondragover = function (e) { e.preventDefault(); this.classList.add('drag-over'); };
        dropArea.ondragleave = function () { this.classList.remove('drag-over'); };
        dropArea.ondrop = function (e) { e.preventDefault(); this.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); };
    }
    if (fileInput) fileInput.onchange = function (e) { handleFiles(e.target.files); };

    function handleFiles(files) {
        if (!files.length) return;
        var arr = [];
        for (var i = 0; i < files.length; i++) arr.push(files[i]);
        // 倒序上传，保证顺序展示自然
        arr.forEach(uploadFile);
        fileInput.value = '';
    }

    // 3. 渲染列表 (带多选框) - 显示所有结果，不分页
    window.renderUploadList = function () {
        var listEl = document.getElementById('uploadBatchList');

        // 保留正在上传的临时卡片 (temp-card)
        var temps = [];
        var children = listEl.children;
        for (var i = 0; i < children.length; i++) {
            if (children[i].classList.contains('temp-card')) temps.push(children[i]);
        }

        listEl.innerHTML = '';
        // 先放回临时卡片
        for (var j = 0; j < temps.length; j++) listEl.appendChild(temps[j]);

        var total = window.allUploadResults.length;

        // 控制工具栏显示
        if (total === 0 && temps.length === 0) {
            if (toolbar) toolbar.style.display = 'none';
            return;
        }
        if (toolbar) toolbar.style.display = 'flex';

        // 渲染所有卡片（不分页）
        window.allUploadResults.forEach(function (data) {
            listEl.appendChild(createResultCard(data));
        });

        // 更新全选框和计数
        updateToolbarState(window.allUploadResults);
    };

    function updateToolbarState(currentSlice) {
        var count = window.uploadSelectedHashes.size;
        if (selectedCount) selectedCount.innerText = count;

        // 全选框状态：如果当前页所有项都被选中，则全选框打钩
        if (selectAll && currentSlice.length > 0) {
            var allChecked = true;
            for (var i = 0; i < currentSlice.length; i++) {
                if (!window.uploadSelectedHashes.has(currentSlice[i].hash)) {
                    allChecked = false;
                    break;
                }
            }
            selectAll.checked = allChecked;
        } else if (selectAll) {
            selectAll.checked = false;
        }
    }

    // 创建卡片 (带复选框)
    function createResultCard(data) {
        var div = document.createElement('div');
        div.className = 'history-card';
        if (window.uploadSelectedHashes.has(data.hash)) {
            div.classList.add('selected');
        }

        var name = getDefaultNameFromResult(data);
        var displayUrl = getFullUrl(data.url);

        // 复选框遮罩
        var checkOverlay = document.createElement('div');
        checkOverlay.className = 'checkbox-overlay';
        checkOverlay.onclick = function (e) { e.stopPropagation(); toggleUploadSelection(data.hash); };

        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'history-checkbox';
        checkbox.checked = window.uploadSelectedHashes.has(data.hash);
        checkbox.onclick = function (e) { e.stopPropagation(); toggleUploadSelection(data.hash); };

        checkOverlay.appendChild(checkbox);
        div.appendChild(checkOverlay);

        // 内容
        var mainRow = document.createElement('div');
        mainRow.className = 'history-main-row';

        // 缩略图
        var img = document.createElement('img');
        img.className = 'history-thumb';
        img.src = displayUrl;
        img.onerror = function () { this.style.opacity = "0.5"; };

        var infoDiv = document.createElement('div');
        infoDiv.className = 'history-info';

        var nameSpan = document.createElement('span');
        nameSpan.className = 'history-name';
        nameSpan.innerText = name;

        // 显示大小
        var sizeSpan = document.createElement('span');
        sizeSpan.style.fontSize = '12px';
        sizeSpan.style.color = 'var(--text-secondary)';
        if (data.size) {
            var kb = (data.size / 1024).toFixed(1);
            sizeSpan.innerText = kb + ' KB';
        }

        infoDiv.appendChild(nameSpan);
        infoDiv.appendChild(sizeSpan);

        var actions = document.createElement('div');
        actions.className = 'history-actions';

        var btnCopy = document.createElement('button');
        btnCopy.className = 'btn-mini';
        btnCopy.innerText = '复制';
        btnCopy.onclick = function () {
            navigator.clipboard.writeText(displayUrl);
            if (window.showToast) window.showToast('已复制', 'success');
        };

        var btnOpen = document.createElement('button');
        btnOpen.className = 'btn-mini';
        btnOpen.innerText = '打开';
        btnOpen.onclick = function () { window.open(displayUrl); };

        var btnRename = document.createElement('button');
        btnRename.className = 'btn-mini';
        btnRename.innerText = '重命名';
        btnRename.onclick = function () {
            var newName = prompt("请输入新的图片名称", name);
            if (newName && newName !== name) {
                // 更新数据
                data.filename = newName;
                window.renderUploadList();
                // 如果需要同步到后端历史记录，这里可能需要额外接口，但目前 upload.js 主要是前端展示
                // 且 history.js 负责历史记录。
                // 如果用户希望重命名能持久化，我们需要调用 history.js 的 renameHistoryByUrl
                if (window.renameHistoryByUrl) {
                    window.renameHistoryByUrl(getFullUrl(data.url), newName);
                }
                if (window.showToast) window.showToast("重命名成功", "success");
            }
        };

        actions.appendChild(btnCopy);
        actions.appendChild(btnOpen);
        actions.appendChild(btnRename);

        mainRow.appendChild(img);
        mainRow.appendChild(infoDiv);
        mainRow.appendChild(actions);

        div.appendChild(mainRow);

        return div;
    }

    function toggleUploadSelection(hash) {
        if (window.uploadSelectedHashes.has(hash)) {
            window.uploadSelectedHashes.delete(hash);
        } else {
            window.uploadSelectedHashes.add(hash);
        }
        window.renderUploadList();
    }

    // 4. 多选工具栏事件绑定
    if (selectAll) {
        selectAll.onclick = function () {
            var target = this.checked;
            // 操作所有项
            window.allUploadResults.forEach(function (item) {
                if (target) window.uploadSelectedHashes.add(item.hash);
                else window.uploadSelectedHashes.delete(item.hash);
            });
            window.renderUploadList();
        };
    }

    if (batchDelBtn) {
        batchDelBtn.onclick = function () {
            var count = window.uploadSelectedHashes.size;
            if (count === 0) return;

            window.allUploadResults = window.allUploadResults.filter(function (item) {
                return !window.uploadSelectedHashes.has(item.hash);
            });

            window.uploadSelectedHashes.clear();
            window.renderUploadList();
            if (window.showToast) window.showToast("已从列表中移除", "success");
        };
    }

    // 新增：批量生成说明文件
    if (batchGenBtn) {
        batchGenBtn.onclick = function () {
            var count = window.uploadSelectedHashes.size;
            if (count === 0) return;

            var targets = [];
            window.allUploadResults.forEach(function (item) {
                if (window.uploadSelectedHashes.has(item.hash)) {
                    targets.push(item);
                }
            });

            var cleaned = cleanUploadDataForExport(targets);
            var jsonStr = JSON.stringify(cleaned, null, 2);
            if (descTextarea) descTextarea.value = jsonStr;
            if (descModal) descModal.style.display = "flex";
        };
    }

    // 5. 核心上传逻辑
    async function uploadFile(file) {
        var batchList = document.getElementById('uploadBatchList');

        // 临时卡片
        var wrapper = document.createElement('div');
        wrapper.className = 'history-card temp-card';
        wrapper.style.opacity = '0.8';
        var localPreviewUrl = URL.createObjectURL(file);
        wrapper.innerHTML =
            '<div class="history-main-row" style="padding-left:12px">' + // 临时卡片不用padding出checkbox位置
            '<img src="' + localPreviewUrl + '" class="history-thumb">' +
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
            formData.append('services', 'myminio');

            bar.style.width = '50%';
            var resp = await fetch('/upload', { method: 'POST', body: formData });
            var res = await resp.json();
            bar.style.width = '100%';

            setTimeout(function () {
                if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);

                if (res.success) {
                    res.url = getFullUrl(res.url);
                    // 去重
                    var oldIdx = -1;
                    for (var k = 0; k < window.allUploadResults.length; k++) {
                        if (window.allUploadResults[k].hash === res.hash) {
                            oldIdx = k;
                            break;
                        }
                    }
                    if (oldIdx !== -1) window.allUploadResults.splice(oldIdx, 1);

                    res.filename = getDefaultNameFromResult(res);

                    window.allUploadResults.unshift(res);
                    window.lastUploadResultUrl = res.url;


                    // 刷新历史记录 (如果已加载)
                    if (typeof window.displayHistory === 'function') window.displayHistory();
                } else {
                    // 错误卡片
                    var div = document.createElement('div');
                    div.className = 'history-card';
                    div.style.borderColor = 'red';
                    div.innerHTML =
                        '<div class="history-main-row" style="padding-left:12px">' +
                        '<div class="history-info">' +
                        '<span class="history-name">' + file.name + '</span>' +
                        '<div style="color:red;font-size:12px;">上传失败: ' + (res.error || '未知') + '</div>' +
                        '</div>' +
                        '</div>';
                    batchList.insertBefore(div, batchList.firstChild);
                }

                window.renderUploadList();
            }, 400);

        } catch (e) {
            console.error(e);
            if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
            if (window.showToast) window.showToast("上传异常: " + e.message, "error");
        }
    }
});
