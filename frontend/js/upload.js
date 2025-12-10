// upload.js - 批量上传 + 多选 + 缩略图修复 + 说明文件生成

window.allUploadResults = [];
window.uploadPage = 1;
window.uploadPageSize = 10;
window.lastUploadResultUrl = null;
window.uploadSelectedHashes = new Set(); // 存储上传列表中被选中的项目 (用 hash 做 key)

// ============ 上传模式状态 ============
// 从 localStorage 读取上传模式（false=私有，true=共享）
window.uploadSharedMode = localStorage.getItem("uploadSharedMode") === "true";

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

        // 添加宽度和高度
        if (item.width) cleanItem.width = item.width;
        if (item.height) cleanItem.height = item.height;

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

    // ============ 上传模式切换 ============
    var uploadModeBtn = document.getElementById('uploadModeBtn');

    function updateUploadModeUI() {
        if (uploadModeBtn) {
            if (window.uploadSharedMode) {
                uploadModeBtn.classList.add('active');
            } else {
                uploadModeBtn.classList.remove('active');
            }
        }
    }

    if (uploadModeBtn) {
        updateUploadModeUI();

        uploadModeBtn.addEventListener('click', function () {
            var token = localStorage.getItem("token");

            // 如果未登录且尝试切换到私有模式，显示提示
            if (!token && window.uploadSharedMode) {
                // 当前是共享模式，用户想切换到私有，但未登录
                if (window.showToast) window.showToast("登录后可使用私有模式", "info");
                return; // 不切换
            }

            window.uploadSharedMode = !window.uploadSharedMode;
            localStorage.setItem("uploadSharedMode", window.uploadSharedMode ? "true" : "false");
            updateUploadModeUI();
        });
    }

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

        // 错误状态处理
        if (data.isError) {
            div.style.borderColor = 'red';
            div.innerHTML =
                '<div class="history-main-row" style="padding-left:12px">' +
                '<div class="history-info">' +
                '<span class="history-name">' + (data.filename || '未知文件') + '</span>' +
                '<div style="color:red;font-size:12px;">上传失败: ' + (data.error || '未知错误') + '</div>' +
                '</div>' +
                '</div>';
            return div;
        }

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

        // 显示哈希值（如果有）
        var hashSpan = document.createElement('span');
        hashSpan.style.fontSize = '11px';
        hashSpan.style.color = 'var(--text-secondary)';
        hashSpan.style.fontFamily = 'monospace';
        if (data.hash) {
            hashSpan.innerText = 'Hash: ' + data.hash;
        }

        // 显示大小
        var sizeSpan = document.createElement('span');
        sizeSpan.style.fontSize = '12px';
        sizeSpan.style.color = 'var(--text-secondary)';
        if (data.size) {
            var kb = (data.size / 1024).toFixed(1);
            sizeSpan.innerText = kb + ' KB';
        }

        infoDiv.appendChild(nameSpan);
        if (data.hash) infoDiv.appendChild(hashSpan);
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
                if (window.renameHistoryItem && data.id) {
                    window.renameHistoryItem(data.id, newName);
                } else if (!data.id) {
                    console.warn("Missing ID for sync rename");
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
            // 添加上传模式参数（私有/共享）
            formData.append('shared_mode', window.uploadSharedMode ? 'true' : 'false');
            // 添加认证 Token
            var authToken = localStorage.getItem('token');
            if (authToken) {
                formData.append('token', authToken);
            }

            bar.style.width = '0%';

            // 使用 XMLHttpRequest 实现真实进度条
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);

            // 进度事件
            if (xhr.upload) {
                xhr.upload.onprogress = function (e) {
                    if (e.lengthComputable) {
                        var percentComplete = (e.loaded / e.total) * 100;
                        bar.style.width = percentComplete + '%';
                    }
                };
            }

            // 完成处理
            xhr.onload = function () {
                if (xhr.status == 200) {
                    var res;
                    try {
                        res = JSON.parse(xhr.responseText);
                        handleUploadSuccess(res);
                    } catch (e) {
                        handleUploadError(file.name, "Invalid Server Response");
                    }
                } else {
                    // 尝试解析服务器返回的错误详情
                    var errorMsg = "服务器错误: " + xhr.status;
                    try {
                        var errRes = JSON.parse(xhr.responseText);
                        if (errRes.detail) {
                            errorMsg = errRes.detail;
                        } else if (errRes.error) {
                            errorMsg = errRes.error;
                        }
                    } catch (e) {
                        // 解析失败，使用默认错误信息
                    }
                    handleUploadError(file.name, errorMsg);
                }
            };

            xhr.onerror = function () {
                handleUploadError(file.name, "Network Error");
            };

            xhr.send(formData);

            function handleUploadSuccess(res) {
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
                        // 错误卡片 - 添加到列表数据中，而不是直接操作DOM
                        window.allUploadResults.unshift({
                            isError: true,
                            filename: file.name,
                            error: res.error || '未知错误',
                            hash: 'error_' + Date.now() + Math.random() // 唯一ID防止冲突
                        });
                    }

                    window.renderUploadList();
                }, 400);
            }

            function handleUploadError(filename, errorMsg) {
                if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
                if (window.showToast) window.showToast("上传异常: " + errorMsg, "error");
            }

        } catch (e) {
            console.error(e);
            if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
            if (window.showToast) window.showToast("上传异常: " + e.message, "error");
        }
    }

    // === 粘贴上传功能 ===
    // 为整个上传标签页添加粘贴事件监听（无需点击上传区域）
    var uploadContent = document.getElementById('content-upload');
    if (uploadContent) {
        uploadContent.addEventListener('paste', async function (e) {
            e.preventDefault();

            var items = (e.clipboardData || e.originalEvent.clipboardData).items;
            var hasImage = false;

            for (var i = 0; i < items.length; i++) {
                var item = items[i];

                // 处理图片文件
                if (item.type.indexOf('image') !== -1) {
                    hasImage = true;
                    var blob = item.getAsFile();
                    if (blob) {
                        // 创建一个File对象
                        var file = new File([blob], 'image.png', { type: blob.type });
                        uploadFile(file);
                    }
                }
                // 处理文本（可能是URL）
                else if (item.type === 'text/plain') {
                    item.getAsString(function (text) {
                        if (/^https?:\/\//i.test(text.trim())) {
                            // 这是一个URL，可以选择处理或忽略
                            if (window.showToast) window.showToast("检测到URL，请直接粘贴图片", "warning");
                        }
                    });
                }
            }

            if (!hasImage) {
                if (window.showToast) window.showToast("剪贴板中没有图片", "warning");
            }
        });
    }
});
