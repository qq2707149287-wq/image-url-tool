"use strict";

// === 核心保存逻辑：合并去重 ===
window.saveToHistory = function(data) {
    try {
        var raw = localStorage.getItem("uploadHistory");
        var list = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(list)) list = [];

        var hash = data.hash || null;
        // 构造本次所有成功的链接列表
        var newLinks = [];
        if (data.all_results && Array.isArray(data.all_results)) {
            newLinks = data.all_results;
        } else if (data.url) {
            newLinks = [{ service: data.service, url: data.url }];
        }

        if (!newLinks.length) return;

        // 1. 查找是否有相同 Hash 的旧记录
        var idx = -1;
        if (hash) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].hash === hash) {
                    idx = i;
                    break;
                }
            }
        }

        if (idx !== -1) {
            // === 合并逻辑 ===
            var item = list[idx];
            // 确保旧记录有 all_results 字段
            if (!item.all_results || !Array.isArray(item.all_results)) {
                item.all_results = [{ service: item.service, url: item.url }];
            }

            // 遍历新链接，不存在的就加进去
            for (var k = 0; k < newLinks.length; k++) {
                var link = newLinks[k];
                var exists = false;
                for (var m = 0; m < item.all_results.length; m++) {
                    if (item.all_results[m].url === link.url) {
                        exists = true;
                        break;
                    }
                }
                if (!exists) {
                    item.all_results.push(link);
                }
            }
            
            // 更新时间和主信息（顶上来）
            item.time = new Date().toLocaleString();
            // 移动到最前面
            list.splice(idx, 1);
            list.unshift(item);

        } else {
            // === 新增逻辑 ===
            var newItem = {
                url: newLinks[0].url, // 主链接
                service: newLinks[0].service,
                filename: data.filename || "未命名",
                time: new Date().toLocaleString(),
                hash: hash,
                all_results: newLinks
            };
            list.unshift(newItem);
        }

        // 限制 200 条
        if (list.length > 200) list = list.slice(0, 200);

        localStorage.setItem("uploadHistory", JSON.stringify(list));

        // 如果当前在历史页面，立即刷新显示
        if (typeof renderHistory === 'function') renderHistory();

    } catch (e) {
        console.error("History save error:", e);
    }
};


// === 页面渲染逻辑 ===
document.addEventListener("DOMContentLoaded", function () {
    var historyList = document.getElementById("historyList");
    if (!historyList) return;

    var clearBtn = document.getElementById("clearHistoryBtn");
    var searchInput = document.getElementById("historySearch");
    var exportBtn = document.getElementById("exportJsonBtn");
    var importBtn = document.getElementById("importJsonBtn");
    var importInput = document.getElementById("importFileInput");
    var tabHistory = document.getElementById("tab-history");

    // 公开给外部使用
    window.displayHistory = renderHistory;

    function renderHistory() {
        var keyword = searchInput ? searchInput.value.trim().toLowerCase() : "";
        var raw = localStorage.getItem("uploadHistory");
        var list = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(list)) list = [];

        historyList.innerHTML = "";

        if (list.length === 0) {
            historyList.innerHTML = '<div class="empty-state">暂无历史记录</div>';
            return;
        }

        list.forEach(function(item) {
            // 搜索过滤
            if (keyword && (item.filename || "").toLowerCase().indexOf(keyword) === -1) return;

            // 准备数据
            var all = item.all_results || [{service: item.service, url: item.url}];
            var displayUrl = item.url || (all[0] ? all[0].url : "");

            // --- 创建 DOM 元素 ---
            var card = document.createElement("div");
            card.className = "history-card";

            // 1. 主行
            var mainRow = document.createElement("div");
            mainRow.className = "history-main-row";
            
            // 左图
            var img = document.createElement("img");
            img.className = "history-thumb";
            img.src = displayUrl;
            img.onerror = function() { this.classList.add("broken"); };

            // 中文
            var infoDiv = document.createElement("div");
            infoDiv.className = "history-info";
            
            var nameRow = document.createElement("div");
            nameRow.className = "history-name-row";
            
            var nameSpan = document.createElement("span");
            nameSpan.className = "history-name";
            nameSpan.textContent = item.filename;
            nameRow.appendChild(nameSpan);

            if (all.length > 1) {
                var badge = document.createElement("span");
                badge.className = "source-badge";
                badge.textContent = all.length + "个源";
                nameRow.appendChild(badge);
            }

            var meta = document.createElement("div");
            meta.className = "history-time";
            meta.textContent = item.time;

            infoDiv.appendChild(nameRow);
            infoDiv.appendChild(meta);

            // 右按钮
            var actions = document.createElement("div");
            actions.className = "history-actions";

            var btnCopy = document.createElement("button");
            btnCopy.className = "btn-mini";
            btnCopy.textContent = "复制";
            btnCopy.onclick = function() {
                navigator.clipboard.writeText(displayUrl);
                if(window.showToast) showToast("已复制");
            };

            var btnOpen = document.createElement("button");
            btnOpen.className = "btn-mini";
            btnOpen.textContent = "打开";
            btnOpen.onclick = function() {
                window.open(displayUrl, "_blank");
            };

            actions.appendChild(btnCopy);
            actions.appendChild(btnOpen);

            // 下拉箭头
            if (all.length > 1) {
                var btnToggle = document.createElement("button");
                btnToggle.className = "btn-mini toggle-btn";
                btnToggle.textContent = "▼";
                btnToggle.onclick = function() {
                    var sub = card.querySelector(".history-sublist");
                    if (sub.style.display === "none") {
                        sub.style.display = "block";
                        this.style.transform = "rotate(180deg)";
                    } else {
                        sub.style.display = "none";
                        this.style.transform = "rotate(0deg)";
                    }
                };
                actions.appendChild(btnToggle);
            }

            mainRow.appendChild(img);
            mainRow.appendChild(infoDiv);
            mainRow.appendChild(actions);
            card.appendChild(mainRow);

            // 2. 子列表
            if (all.length > 1) {
                var subList = document.createElement("div");
                subList.className = "history-sublist";
                subList.style.display = "none";

                all.forEach(function(sub) {
                    var row = document.createElement("div");
                    row.className = "sub-row";
                    
                    // 必须使用 textContent 防止 XSS，千万别用 innerHTML 拼接长字符串
                    var tag = document.createElement("span");
                    tag.className = "sub-tag";
                    tag.textContent = sub.service;

                    var link = document.createElement("a");
                    link.className = "sub-link";
                    link.href = sub.url;
                    link.target = "_blank";
                    link.textContent = sub.url;

                    var copySub = document.createElement("button");
                    copySub.className = "btn-text-sm";
                    copySub.textContent = "复制";
                    copySub.onclick = function() {
                        navigator.clipboard.writeText(sub.url);
                        if(window.showToast) showToast("已复制 " + sub.service);
                    };

                    row.appendChild(tag);
                    row.appendChild(link);
                    row.appendChild(copySub);
                    subList.appendChild(row);
                });
                card.appendChild(subList);
            }

            historyList.appendChild(card);
        });
    }

    // 绑定事件
    if (searchInput) searchInput.oninput = renderHistory;
    if (tabHistory) tabHistory.onclick = renderHistory;
    
    if (clearBtn) {
        clearBtn.onclick = function() {
            if (confirm("确定清空所有历史记录？")) {
                localStorage.removeItem("uploadHistory");
                renderHistory();
            }
        };
    }

    // 导出功能（修复变量名防截断）
    if (exportBtn) {
        exportBtn.onclick = function() {
            var list = JSON.parse(localStorage.getItem("uploadHistory") || "[]");
            if (!list.length) {
                alert("无记录");
                return;
            }
            var str = JSON.stringify(list, null, 2);
            var arr = [];
            arr.push(str);
            var b = new Blob(arr, {type: "application/json"});
            var url = URL.createObjectURL(b);
            var a = document.createElement("a");
            a.href = url;
            a.download = "history_backup.json";
            a.click();
        };
    }
    
    // 导入功能
    if (importBtn && importInput) {
        importBtn.onclick = function() { importInput.click(); };
        importInput.onchange = function() {
            var f = importInput.files[0];
            if (!f) return;
            var r = new FileReader();
            r.onload = function(e) {
                try {
                    var d = JSON.parse(e.target.result);
                    if (!Array.isArray(d)) throw new Error();
                    localStorage.setItem("uploadHistory", JSON.stringify(d));
                    renderHistory();
                    alert("导入成功");
                } catch(x) { alert("格式错误"); }
            };
            r.readAsText(f);
        };
    }

    // 初始渲染
    renderHistory();
});
