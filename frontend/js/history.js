"use strict";

window.historyPage = 1;
window.historyPageSize = 10;
window.historyTotal = 0;
window.selectedIds = new Set(); // 使用 ID 进行多选，更准确

// ============ 查看模式状态 ============
// viewMode: "private"(私有图片) 或 "shared"(共享图片)
// 如果未登录，强制默认为 "shared"
var initialViewMode = localStorage.getItem("viewMode") || "private";
if (!localStorage.getItem("token")) {
    initialViewMode = "shared";
}
window.viewMode = initialViewMode;
// onlyMine: 在共享模式下是否只看自己的共享图片
window.onlyMine = localStorage.getItem("onlyMine") === "true";

// ============ 时间格式化工具 ============

/**
 * 将 UTC 时间字符串转换为用户本地时区的格式化时间
 * @param {string} utcTimeStr - UTC 时间字符串，格式如 "2024-01-15 10:30:00" 或 "2024-01-15T10:30:00"
 * @returns {string} 本地时区的格式化时间字符串
 */
function formatLocalTime(utcTimeStr) {
    if (!utcTimeStr) return "";

    try {
        // SQLite CURRENT_TIMESTAMP 格式: "2024-01-15 10:30:00"
        // 需要将其转换为 ISO 格式并标记为 UTC
        var normalized = utcTimeStr.trim().replace(" ", "T");
        // 如果没有时区标记，添加 Z 表示 UTC
        if (!normalized.endsWith("Z") && !normalized.includes("+") && !normalized.includes("-", 10)) {
            normalized += "Z";
        }

        var date = new Date(normalized);

        // 检查日期是否有效
        if (isNaN(date.getTime())) {
            return utcTimeStr.replace("T", " ").split(".")[0];
        }

        // 使用用户本地时区格式化
        // 格式: YYYY-MM-DD HH:mm:ss
        var year = date.getFullYear();
        var month = String(date.getMonth() + 1).padStart(2, "0");
        var day = String(date.getDate()).padStart(2, "0");
        var hours = String(date.getHours()).padStart(2, "0");
        var minutes = String(date.getMinutes()).padStart(2, "0");
        var seconds = String(date.getSeconds()).padStart(2, "0");

        return year + "-" + month + "-" + day + " " + hours + ":" + minutes + ":" + seconds;
    } catch (e) {
        // 解析失败时返回原始字符串的简单处理
        return utcTimeStr.replace("T", " ").split(".")[0];
    }
}

// ============ 数据清洗工具 (生成说明文件用) ============
function cleanDataForExport(dataList) {
    var result = [];
    for (var i = 0; i < dataList.length; i++) {
        var item = dataList[i];
        var cleanItem = {};

        // 保留字段 - 确保URL是完整的
        if (item.url) {
            // 补全URL
            var fullUrl = item.url;
            if (!fullUrl.startsWith("http")) {
                if (fullUrl.startsWith("/")) {
                    fullUrl = window.location.origin + fullUrl;
                }
            }
            cleanItem.url = fullUrl;
        }
        if (item.filename) cleanItem.filename = item.filename;

        // 添加宽度和高度
        if (item.width) cleanItem.width = item.width;
        if (item.height) cleanItem.height = item.height;

        // 添加带单位的文件大小
        if (item.size) {
            var sizeInKB = (item.size / 1024).toFixed(2);
            cleanItem.size = sizeInKB + ' KB';
        }

        // 提取 content_type
        if (item.content_type) {
            cleanItem.content_type = item.content_type;
        } else if (item.all_results && Array.isArray(item.all_results) && item.all_results.length > 0 && item.all_results[0].content_type) {
            cleanItem.content_type = item.all_results[0].content_type;
        }

        // 移除 service, time, hash, linkstatus (不添加即可)

        result.push(cleanItem);
    }
    return result;
}

// ============ DOM 初始化 ============
document.addEventListener("DOMContentLoaded", function () {
    var historyList = document.getElementById("historyList");
    // 如果页面没有历史记录相关元素，直接返回
    if (!historyList) return;

    var clearBtn = document.getElementById("clearHistoryBtn");
    var searchInput = document.getElementById("historySearch");
    var tabHistory = document.getElementById("tab-history");
    var paginationBar = document.getElementById("historyPagination");
    var pageInfoText = document.getElementById("historyPageInfo");
    var pageSizeSelect = document.getElementById("historyPageSizeSelect");

    var selectAllBox = document.getElementById("selectAllCheckbox");
    var multiActions = document.getElementById("multiActions");
    var selectedCountSpan = document.getElementById("selectedCount");
    var batchDelBtn = document.getElementById("batchDeleteBtn");
    var batchGenBtn = document.getElementById("batchGenerateDescBtn");

    var descModal = document.getElementById("descModal");
    var descTextarea = document.getElementById("descTextarea");
    var copyDescBtn = document.getElementById("copyDescBtn");
    var downloadDescBtn = document.getElementById("downloadDescBtn");

    // 查看模式切换相关
    var viewModeBtn = document.getElementById("viewModeBtn");
    var onlyMineFilter = document.getElementById("onlyMineFilter");
    var onlyMineCheckbox = document.getElementById("onlyMineCheckbox");

    // 初始化查看模式UI
    function updateViewModeUI() {
        var isSharedView = window.viewMode === "shared";

        if (viewModeBtn) {
            if (isSharedView) {
                viewModeBtn.classList.add('active');
            } else {
                viewModeBtn.classList.remove('active');
            }
        }
        // 只在共享模式下显示"只看我的"筛选 (后端支持 device_id 过滤)
        if (onlyMineFilter) {
            onlyMineFilter.style.display = isSharedView ? "flex" : "none";
        }
        if (onlyMineCheckbox) {
            onlyMineCheckbox.checked = window.onlyMine;
        }
    }

    // 切换查看模式
    if (viewModeBtn) {
        // 初始化状态
        updateViewModeUI();

        viewModeBtn.onclick = function () {
            // 检查登录状态 (简单判断 token)
            var token = localStorage.getItem("token");
            if (!token) {
                if (window.showToast) window.showToast("匿名用户仅支持查看共享模式", "warning");
                // 强制保持 shared
                window.viewMode = "shared";
                updateViewModeUI();
                return;
            }

            window.viewMode = window.viewMode === "shared" ? "private" : "shared";
            localStorage.setItem("viewMode", window.viewMode);
            updateViewModeUI();

            var msg = window.viewMode === "shared"
                ? "正在查看共享图片"
                : "正在查看私有图片";
            if (window.showToast) window.showToast(msg, "info");

            // 重新加载历史记录
            window.historyPage = 1;
            loadHistory();
        };
    }

    // "只看我的"筛选
    if (onlyMineCheckbox) {
        onlyMineCheckbox.onchange = function () {
            window.onlyMine = this.checked;
            localStorage.setItem("onlyMine", window.onlyMine ? "true" : "false");

            // 重新加载历史记录
            window.historyPage = 1;
            loadHistory();
        };
    }

    // ============ 工具函数 ============
    // [Admin] 强制进入审计模式
    window.forceAdminAuditMode = function () {
        // 设置一个临时标记，不保存到 localStorage (刷新即失效，避免影响正常使用)
        window.isAdminAudit = true;
        // 强制重置页码
        window.historyPage = 1;
        // 刷新列表
        loadHistory();
        if (window.showToast) window.showToast("👁️ 上帝模式已开启：正在查看全站所有文件", "warning");
    };

    // 重命名历史记录（通过URL）
    window.renameHistoryByUrl = function (url, newName) {
        // 发送请求到后端更新数据库中的filename
        var headers = { "Content-Type": "application/json" };
        var token = localStorage.getItem("token");
        if (token) headers["Authorization"] = "Bearer " + token;

        fetch("/history/rename", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ url: url, filename: newName })
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    // 刷新当前页面的历史记录
                    loadHistory();
                } else {
                    if (window.showToast) window.showToast("重命名失败: " + (data.error || "未知错误"), "error");
                }
            })
            .catch(function (err) {
                console.error(err);
                if (window.showToast) window.showToast("网络错误", "error");
            });
    };

    // ============ 加载历史记录 (API) ============
    function loadHistory() {
        var keyword = searchInput ? searchInput.value.trim() : "";
        var url = "/history?page=" + window.historyPage + "&page_size=" + window.historyPageSize;
        if (keyword) {
            url += "&keyword=" + encodeURIComponent(keyword);
        }

        // 处理查看模式
        var currentMode = window.viewMode;

        // [Admin] 如果处于上帝审计模式，覆盖 view_mode 参数
        if (window.isAdminAudit) {
            currentMode = "admin_all";

            // 更新UI状态暗示处于特殊模式
            if (viewModeBtn) {
                viewModeBtn.classList.remove('active'); // 既不是 private 也不是 shared 的正常态
                viewModeBtn.style.opacity = "0.5";
                viewModeBtn.title = "当前处于上帝视角，点击退出";
                viewModeBtn.onclick = function () {
                    // 点击退出审计模式
                    window.isAdminAudit = false;
                    viewModeBtn.style.opacity = "1";
                    viewModeBtn.title = "";
                    // 恢复正常 toggle
                    this.onclick = function () {
                        // ... 原 toggle 逻辑 ...
                        // (为了简单，直接刷新页面恢复状态最安全)
                        location.reload();
                    };
                    location.reload();
                };
            }
        }

        // 添加查看模式参数
        url += "&view_mode=" + encodeURIComponent(currentMode);
        // 在共享模式下，添加"只看我的"参数
        if (currentMode === "shared" && window.onlyMine) {
            url += "&only_mine=true";
        }

        var headers = {};
        var token = localStorage.getItem("token");
        if (token) headers["Authorization"] = "Bearer " + token;

        fetch(url, { headers: headers })
            .then(function (res) { return res.json(); })
            .then(function (res) {
                if (res.success) {
                    window.historyTotal = res.total;
                    renderHistoryList(res.data);
                    updatePagination();
                } else {
                    if (window.showToast) window.showToast("加载历史记录失败: " + res.error, "error");
                }
            })
            .catch(function (err) {
                console.error(err);
                if (window.showToast) window.showToast("网络错误", "error");
            });
    }

    // ============ 渲染列表 ============
    function renderHistoryList(list) {
        historyList.innerHTML = "";
        window.currentHistoryData = list; // 保存当前页数据供全选使用

        if (!list || list.length === 0) {
            historyList.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-secondary)">暂无历史记录</div>';
            if (paginationBar) paginationBar.style.display = 'none';
            // 重置多选状态
            if (selectAllBox) {
                selectAllBox.checked = false;
                selectAllBox.disabled = true;
            }
            return;
        }

        if (paginationBar) paginationBar.style.display = 'flex';
        // 匿名用户禁止删除/操作 (除非有 token)
        var token = localStorage.getItem("token");
        if (selectAllBox) selectAllBox.disabled = !token;

        // 检查全选状态
        updateSelectAllState(list);

        for (var i = 0; i < list.length; i++) {
            historyList.appendChild(createHistoryCard(list[i]));
        }

        updateMultiActionState();
    }

    function updatePagination() {
        if (!pageInfoText) return;
        var totalPages = Math.ceil(window.historyTotal / window.historyPageSize);
        if (totalPages < 1) totalPages = 1;
        pageInfoText.innerText = window.historyPage + " / " + totalPages;
    }

    // ============ 创建卡片 ============
    function createHistoryCard(item) {
        var card = document.createElement("div");
        card.className = "history-card";
        if (window.selectedIds.has(item.id)) {
            card.classList.add("selected");
        }

        // 复选框区域
        // 复选框区域
        var checkOverlay = document.createElement("div");
        checkOverlay.className = "checkbox-overlay";
        checkOverlay.onclick = function (e) { e.stopPropagation(); toggleSelection(item.id); };

        var checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "history-checkbox";
        checkbox.checked = window.selectedIds.has(item.id);
        checkbox.onclick = function (e) { e.stopPropagation(); toggleSelection(item.id); };

        checkOverlay.appendChild(checkbox);
        card.appendChild(checkOverlay);

        // 主内容
        var mainRow = document.createElement("div");
        mainRow.className = "history-main-row";

        // 补全URL
        var fullUrl = item.url;
        if (!fullUrl.startsWith("http")) {
            if (fullUrl.startsWith("/")) {
                fullUrl = window.location.origin + fullUrl;
            }
        }

        // 缩略图
        var img = document.createElement("img");
        img.className = "history-thumb";
        img.src = fullUrl;
        img.onerror = function () {
            // [FIX v2] 显示失效占位，30分钟后自动删除
            this.onerror = null; // 防止无限递归
            this.src = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PHJlY3Qgd2lkdGg9IjEwMCIgaGVpZ2h0PSIxMDAiIGZpbGw9IiNmNWY1ZjUiLz48dGV4dCB4PSI1MCIgeT0iNTAiIGZvbnQtZmFtaWx5PSJhcmlhbCIgZm9udC1zaXplPSIxMiIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuWbvueJh+S4ouWksSE8L3RleHQ+PC9zdmc+";
            this.style.opacity = "0.8";
            this.style.border = "1px dashed #d32f2f";
            this.title = "⚠️ 图片文件在存储中未找到 (404)，将在30分钟后自动清理";

            // 标记卡片状态
            card.classList.add("history-invalid");

            // 显示错误提示和倒计时
            var errorTag = document.createElement("div");
            errorTag.innerText = "文件丢失 (30分钟后删除)";
            errorTag.style.position = "absolute";
            errorTag.style.bottom = "0";
            errorTag.style.left = "0";
            errorTag.style.width = "100%";
            errorTag.style.background = "rgba(211, 47, 47, 0.9)";
            errorTag.style.color = "white";
            errorTag.style.fontSize = "10px";
            errorTag.style.textAlign = "center";
            errorTag.style.padding = "2px 0";
            img.parentElement.style.position = "relative";
            img.parentElement.appendChild(errorTag);

            // 30分钟后自动删除 (1800000ms)
            var deleteDelay = 30 * 60 * 1000;
            var itemId = item.id; // 闭包保存 ID

            setTimeout(function () {
                var headers = { "Content-Type": "application/json" };
                var token = localStorage.getItem("token");
                if (token) headers["Authorization"] = "Bearer " + token;

                fetch("/history/delete", {
                    method: "POST",
                    headers: headers,
                    body: JSON.stringify({ ids: [itemId] })
                }).then(function (res) {
                    if (res.ok) {
                        console.log("[Auto Clean] 已删除失效记录 ID:", itemId);
                        // 从 DOM 移除卡片 (如果还在页面上)
                        if (card.parentElement) {
                            card.style.transition = "opacity 0.3s";
                            card.style.opacity = "0";
                            setTimeout(function () { card.remove(); }, 300);
                        }
                    }
                }).catch(function (e) {
                    console.warn("[Auto Clean] 删除失败:", e);
                });
            }, deleteDelay);
        };

        var infoDiv = document.createElement("div");
        infoDiv.className = "history-info";

        var nameSpan = document.createElement("span");
        nameSpan.className = "history-name";
        nameSpan.textContent = item.filename || "未命名";
        nameSpan.title = item.filename; // tooltip
        infoDiv.appendChild(nameSpan);

        // 显示哈希值（如果有）
        if (item.hash) {
            var hashSpan = document.createElement("span");
            hashSpan.style.fontSize = "11px";
            hashSpan.style.color = "var(--text-secondary)";
            hashSpan.style.fontFamily = "monospace";
            hashSpan.textContent = "Hash: " + item.hash;
            infoDiv.appendChild(hashSpan);
        }

        var meta = document.createElement("div");
        meta.className = "history-time";
        // 格式化时间：将 UTC 时间转换为用户本地时区
        var timeStr = formatLocalTime(item.created_at);
        meta.textContent = timeStr;
        infoDiv.appendChild(meta);

        // 按钮组
        var actions = document.createElement("div");
        actions.className = "history-actions";

        var btnShare = document.createElement("button");
        btnShare.className = "btn-mini btn-primary";
        btnShare.textContent = "获取链接";
        btnShare.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        btnShare.style.color = 'white';
        btnShare.style.border = 'none';

        btnShare.onclick = function (e) {
            e.stopPropagation();

            // 构造 View URL
            // History item 可能没有返回 hash (取决于 backend query)
            // 检查 item 结构: item.url, item.filename, item.size, item.hash
            var viewUrl = "";
            if (item.hash) {
                viewUrl = window.location.origin + "/view/" + item.hash;
            } else {
                // 如果没有 Hash，只能用 URL 猜测? 或者 Fallback 到 Raw URL
                // 暂时用 fullUrl (虽然不是 landing page)
                viewUrl = fullUrl;
            }

            var modalData = {
                url: item.url, // Raw path /mycloud/...
                viewUrl: viewUrl,
                filename: item.filename,
                size: item.size, // 传递数值，Modal 会自己格式化
                hash: item.hash || "",
                thumb_url: fullUrl // 列表里显示的图
            };

            window.openShareModal(modalData);
        };

        var btnRename = document.createElement("button");
        btnRename.className = "btn-mini";
        btnRename.textContent = "重命名";

        // 只有自己的记录才能重命名
        if (item.is_mine === false) {
            btnRename.disabled = true;
            btnRename.style.opacity = "0.5";
            btnRename.style.cursor = "not-allowed";
            btnRename.title = "无法重命名他人的共享记录";
        } else {
            btnRename.onclick = function (e) {
                e.stopPropagation();
                var newName = prompt("请输入新名称:", item.filename);
                if (newName && newName.trim() !== "" && newName !== item.filename) {
                    if (window.renameHistoryItem) {
                        window.renameHistoryItem(item.id, newName.trim());
                    }
                }
            };
        }

        actions.appendChild(btnShare);

        // 打开按钮
        var btnOpen = document.createElement("button");
        btnOpen.className = "btn-mini";
        btnOpen.textContent = "打开";
        btnOpen.onclick = function (e) {
            e.stopPropagation();
            // 打开查看页面（如果有 hash）或直接打开原图
            var openUrl = item.hash ? (window.location.origin + "/view/" + item.hash) : fullUrl;
            window.open(openUrl, "_blank");
        };
        actions.appendChild(btnOpen);

        actions.appendChild(btnRename);

        mainRow.appendChild(img);
        mainRow.appendChild(infoDiv);
        mainRow.appendChild(actions);
        card.appendChild(mainRow);

        return card;
    }

    // ============ 多选逻辑 ============
    function toggleSelection(id) {
        if (window.selectedIds.has(id)) window.selectedIds.delete(id);
        else window.selectedIds.add(id);

        // 重新渲染当前列表以更新样式
        renderHistoryList(window.currentHistoryData || []);
    }

    function updateSelectAllState(list) {
        if (!selectAllBox) return;
        var allSelected = true;
        for (var i = 0; i < list.length; i++) {
            if (!window.selectedIds.has(list[i].id)) {
                allSelected = false;
                break;
            }
        }
        selectAllBox.checked = allSelected;
    }

    function updateMultiActionState() {
        var count = window.selectedIds.size;
        if (selectedCountSpan) selectedCountSpan.innerText = String(count);
        if (multiActions) multiActions.style.display = count > 0 ? "flex" : "none";
    }

    // 全选/反选 (仅针对当前页)
    if (selectAllBox) {
        selectAllBox.onclick = function () {
            var targetState = this.checked;
            var list = window.currentHistoryData || [];
            for (var i = 0; i < list.length; i++) {
                if (targetState) window.selectedIds.add(list[i].id);
                else window.selectedIds.delete(list[i].id);
            }
            renderHistoryList(list);
        };
    }

    // ============ 批量删除 (API) ============
    if (batchDelBtn) {
        batchDelBtn.onclick = function () {
            var count = window.selectedIds.size;
            if (count === 0) return;
            if (!confirm("确定删除选中的 " + count + " 项记录吗？(数据库删除不可恢复)")) return;

            var ids = Array.from(window.selectedIds);

            var ids = Array.from(window.selectedIds);

            var headers = { "Content-Type": "application/json" };
            var token = localStorage.getItem("token");
            if (token) headers["Authorization"] = "Bearer " + token;

            fetch("/history/delete", {
                method: "POST",
                headers: headers,
                body: JSON.stringify({ ids: ids })
            })
                .then(function (res) { return res.json(); })
                .then(function (res) {
                    if (res.success) {
                        if (window.showToast) window.showToast("已删除 " + res.count + " 项", "success");
                        window.selectedIds.clear();
                        loadHistory(); // 刷新列表
                    } else {
                        alert("删除失败: " + res.error);
                    }
                })
                .catch(function (e) {
                    console.error(e);
                    alert("网络错误");
                });
        };
    }

    // ============ 批量生成说明文件 ============
    if (batchGenBtn) {
        batchGenBtn.onclick = function () {
            var count = window.selectedIds.size;
            if (count === 0) return;

            // 我们需要获取选中项的完整数据。
            // 由于分页，选中的ID可能不在当前页。
            // 简单起见，我们只支持对当前页已加载的数据生成，或者需要后端支持根据ID获取详情。
            // 这里我们遍历 currentHistoryData，如果 ID 在 selectedIds 里则选中。
            // *注意*: 如果用户跨页选了，这里的逻辑只能处理当前页的数据。
            // 为了支持跨页，我们需要在前端缓存所有选中的 item 数据，或者请求后端。
            // 鉴于复杂度，目前仅支持处理当前页选中的数据，或者我们尝试在 selectedIds 里存对象？
            // 为了稳健，我们暂时只处理当前页的选中项。如果用户翻页了，数据可能丢失。
            // 改进：selectedIds 只存 ID，但为了生成文件，我们需要数据。
            // 方案：遍历 currentHistoryData。如果用户需要跨页导出，建议增加“获取选中项详情”的接口。
            // 简化方案：仅导出当前页选中的项。

            var targets = [];
            var list = window.currentHistoryData || [];
            for (var i = 0; i < list.length; i++) {
                if (window.selectedIds.has(list[i].id)) {
                    targets.push(list[i]);
                }
            }

            if (targets.length === 0 && window.selectedIds.size > 0) {
                alert("只能生成当前页显示的记录说明文件。请在当前页选择。");
                return;
            }

            var cleaned = cleanDataForExport(targets);
            var jsonStr = JSON.stringify(cleaned, null, 2);
            if (descTextarea) descTextarea.value = jsonStr;
            if (descModal) descModal.style.display = "flex";
        };
    }

    // ============ 模态框操作 ============
    if (copyDescBtn) {
        copyDescBtn.onclick = function () {
            if (!descTextarea) return;
            descTextarea.select();
            document.execCommand("copy");
            if (window.showToast) window.showToast("文本已复制", "success");
        };
    }

    if (downloadDescBtn) {
        downloadDescBtn.onclick = function () {
            if (!descTextarea) return;
            var content = descTextarea.value;
            var blob = new Blob([content], { type: "application/json;charset=utf-8" });
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = "image_descriptions_" + Date.now() + ".json";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            if (window.showToast) window.showToast("文件已生成", "success");
        };
    }

    // ============ 清空全部 (API) ============
    if (clearBtn) {
        clearBtn.onclick = function () {
            var modeName = window.viewMode === "shared" ? "共享" : "私有";
            if (window.confirm("确定清空所有【" + modeName + "】历史记录？此操作不可恢复！")) {
                var headers = {};
                var token = localStorage.getItem("token");
                if (token) headers["Authorization"] = "Bearer " + token;

                // 添加 view_mode 参数
                fetch("/history/clear?view_mode=" + encodeURIComponent(window.viewMode), {
                    method: "POST",
                    headers: headers
                })
                    .then(function (res) { return res.json(); })
                    .then(function (res) {
                        if (res.success) {
                            window.selectedIds.clear();
                            loadHistory();
                            if (window.showToast) window.showToast(modeName + "历史记录已清空", "success");
                        } else {
                            alert("清空失败: " + res.error);
                        }
                    });
            }
        }
    }

    // ============ 搜索 ============
    var searchTimer;
    if (searchInput) {
        searchInput.oninput = function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function () {
                window.historyPage = 1;
                loadHistory();
            }, 300);
        };
    }

    // ============ 分页控制 ============
    window.prevHistoryPage = function () {
        if (window.historyPage > 1) {
            window.historyPage--;
            loadHistory();
        }
    };
    window.nextHistoryPage = function () {
        var max = Math.ceil(window.historyTotal / window.historyPageSize);
        if (window.historyPage < max) {
            window.historyPage++;
            loadHistory();
        }
    };
    window.changeHistoryPageSize = function (val) {
        window.historyPageSize = parseInt(val, 10);
        window.historyPage = 1;
        loadHistory();
    };

    // ============ 暴露给全局的刷新函数 ============
    window.displayHistory = function () {
        loadHistory();
    };

    // ============ 初始化 ============
    // 如果当前是在历史记录 tab，立即加载
    if (tabHistory && tabHistory.classList.contains("active")) {
        loadHistory();
    }

    // 监听 Tab 切换
    if (tabHistory) {
        tabHistory.addEventListener("click", function () {
            loadHistory();
        });
    }
    // ============ 重命名 (API) ============
    window.renameHistoryItem = function (id, newName) {
        if (!id) return;
        if (!newName || newName.trim() === "") return;

        var headers = { "Content-Type": "application/json" };
        var token = localStorage.getItem("token");
        if (token) headers["Authorization"] = "Bearer " + token;

        fetch("/history/rename", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ id: id, filename: newName })
        })
            .then(function (res) { return res.json(); })
            .then(function (res) {
                if (res.success) {
                    if (window.showToast) window.showToast("重命名成功", "success");
                    loadHistory();
                } else {
                    alert("重命名失败: " + res.error);
                }
            })
            .catch(function (e) {
                console.error(e);
                alert("网络错误");
            });
    };
});

