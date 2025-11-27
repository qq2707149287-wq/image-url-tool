"use strict";

window.historyPage = 1;
window.historyPageSize = 10;
window.historyFilteredData = [];

// 保存历史
window.saveToHistory = function(data) {
    try {
        var raw = localStorage.getItem("uploadHistory");
        var list = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(list)) list = [];

        var hash = data.hash || null;
        var newLinks = [];
        if (data.all_results && Array.isArray(data.all_results)) {
            newLinks = data.all_results;
        } else if (data.url) {
            newLinks = [{ service: data.service, url: data.url }];
        }
        if (!newLinks.length) return;

        var idx = -1;
        if (hash) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].hash === hash) {
                    idx = i;
                    break;
                }
            }
        } else {
            for (var j = 0; j < list.length; j++) {
                if (list[j].url === data.url) {
                    idx = j;
                    break;
                }
            }
        }

        if (idx !== -1) {
            var item = list[idx];
            if (!item.all_results || !Array.isArray(item.all_results)) {
                item.all_results = [{ service: item.service, url: item.url }];
            }
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
            item.time = new Date().toLocaleString();
            item.url = data.url;
            item.filename = data.filename || item.filename || "未命名";
            list.splice(idx, 1);
            list.unshift(item);
        } else {
            var newItem = {
                url: newLinks[0].url,
                service: newLinks[0].service,
                filename: data.filename || "未命名",
                time: new Date().toLocaleString(),
                hash: hash,
                all_results: newLinks,
                linkStatus: data.linkStatus || "unknown"
            };
            list.unshift(newItem);
        }

        if (list.length > 500) list = list.slice(0, 500);
        localStorage.setItem("uploadHistory", JSON.stringify(list));

        if (typeof window.displayHistory === "function") {
            window.displayHistory();
        }
    } catch (e) {
        console.error("History save error:", e);
    }
};

// 新增：按 URL 重命名（上传页、粘贴页、公用）
window.renameHistoryByUrl = function(url, newName) {
    if (!url || !newName) return;
    try {
        var raw = localStorage.getItem("uploadHistory");
        var list = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(list)) list = [];

        var changed = false;
        for (var i = 0; i < list.length; i++) {
            if (list[i].url === url) {
                list[i].filename = newName;
                changed = true;
                break;
            }
        }
        if (!changed) return;

        localStorage.setItem("uploadHistory", JSON.stringify(list));
        if (typeof window.displayHistory === "function") {
            window.displayHistory();
        }
    } catch (e) {
        console.error("renameHistoryByUrl error:", e);
    }
};

document.addEventListener("DOMContentLoaded", function () {
    var historyList = document.getElementById("historyList");
    if (!historyList) return;

    var clearBtn      = document.getElementById("clearHistoryBtn");
    var searchInput   = document.getElementById("historySearch");
    var exportBtn     = document.getElementById("exportJsonBtn");
    var importBtn     = document.getElementById("importJsonBtn");
    var importInput   = document.getElementById("importFileInput");
    var tabHistory    = document.getElementById("tab-history");
    var paginationBar = document.getElementById("historyPagination");
    var pageInfoText  = document.getElementById("historyPageInfo");

    function renderHistory() {
        var keyword = searchInput ? searchInput.value.trim().toLowerCase() : "";
        var raw = localStorage.getItem("uploadHistory");
        var list = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(list)) list = [];

        historyList.innerHTML = "";

        var filteredList = list.filter(function(item) {
            if (!keyword) return true;
            return (item.filename || "").toLowerCase().indexOf(keyword) !== -1 ||
                   (item.url || "").toLowerCase().indexOf(keyword) !== -1;
        });
        
        window.historyFilteredData = filteredList;

        if (filteredList.length === 0) {
            historyList.innerHTML = '<div class="empty-state" style="text-align:center;padding:20px;color:#999">暂无历史记录</div>';
            if (paginationBar) paginationBar.style.display = 'none';
            return;
        }

        if (paginationBar) paginationBar.style.display = 'flex';
        
        var totalPages = Math.ceil(filteredList.length / window.historyPageSize);
        if (totalPages < 1) totalPages = 1;
        if (window.historyPage > totalPages) window.historyPage = totalPages;
        if (window.historyPage < 1) window.historyPage = 1;

        if (pageInfoText) pageInfoText.innerText = window.historyPage + " / " + totalPages;

        var start = (window.historyPage - 1) * window.historyPageSize;
        var end = start + window.historyPageSize;
        var pageItems = filteredList.slice(start, end);

        pageItems.forEach(function(item) {
            var all = item.all_results || [{service: item.service, url: item.url}];
            var displayUrl = item.url || (all[0] ? all[0].url : "");

            var card = document.createElement("div");
            card.className = "history-card";
            card.setAttribute("data-url", displayUrl); 

            var mainRow = document.createElement("div");
            mainRow.className = "history-main-row";
            
            var img = document.createElement("img");
            img.className = "history-thumb";
            img.src = displayUrl;
            img.onerror = function() { this.classList.add("broken"); };

            var infoDiv = document.createElement("div");
            infoDiv.className = "history-info";
            
            var nameRow = document.createElement("div");
            nameRow.className = "history-name-row";
            
            var nameSpan = document.createElement("span");
            nameSpan.className = "history-name";
            nameSpan.textContent = item.filename || "未命名";
            nameSpan.title = item.filename || "未命名";
            nameRow.appendChild(nameSpan);

            if (all.length > 1) {
                var badge = document.createElement("span");
                badge.className = "source-badge";
                badge.textContent = all.length + "个源";
                nameRow.appendChild(badge);
            } else {
                var badgeS = document.createElement("span");
                badgeS.className = "source-badge";
                badgeS.textContent = item.service || "MyCloud";
                nameRow.appendChild(badgeS);
            }

            var meta = document.createElement("div");
            meta.className = "history-time";
            meta.textContent = item.time || "";

            infoDiv.appendChild(nameRow);
            infoDiv.appendChild(meta);

            var actions = document.createElement("div");
            actions.className = "history-actions";

            var btnCopy = document.createElement("button");
            btnCopy.className = "btn-mini";
            btnCopy.textContent = "复制";
            btnCopy.onclick = function() {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(displayUrl);
                } else {
                    var ta = document.createElement("textarea");
                    ta.value = displayUrl;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand("copy");
                    document.body.removeChild(ta);
                }
                if (window.showToast) window.showToast("已复制");
                else alert("已复制");
            };

            var btnOpen = document.createElement("button");
            btnOpen.className = "btn-mini";
            btnOpen.textContent = "打开";
            btnOpen.onclick = function() {
                window.open(displayUrl, "_blank");
            };

            // 新增：重命名按钮
            var btnRename = document.createElement("button");
            btnRename.className = "btn-mini";
            btnRename.textContent = "重命名";
            btnRename.onclick = function () {
                var current = item.filename || "";
                var newName = window.prompt("输入新的图片名称", current);
                if (!newName) return;
                window.renameHistoryByUrl(displayUrl, newName);
            };

            actions.appendChild(btnCopy);
            actions.appendChild(btnOpen);
            actions.appendChild(btnRename);

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

            if (all.length > 1) {
                var subList = document.createElement("div");
                subList.className = "history-sublist";
                subList.style.display = "none";

                all.forEach(function(sub) {
                    var row = document.createElement("div");
                    row.className = "sub-row";
                    
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
                    copySub.style.marginLeft = "auto";
                    copySub.onclick = function() {
                        navigator.clipboard.writeText(sub.url);
                        if (window.showToast) window.showToast("已复制 " + sub.service);
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

    window.displayHistory = renderHistory;

    window.prevHistoryPage = function() {
        if (window.historyPage > 1) {
            window.historyPage--;
            renderHistory();
        }
    };
    window.nextHistoryPage = function() {
        var max = Math.ceil(window.historyFilteredData.length / window.historyPageSize);
        if (window.historyPage < max) {
            window.historyPage++;
            renderHistory();
        }
    };
    window.changeHistoryPageSize = function(val) {
        window.historyPageSize = parseInt(val, 10);
        window.historyPage = 1;
        renderHistory();
    };

    if (searchInput) {
        searchInput.oninput = function() {
            window.historyPage = 1;
            renderHistory();
        };
    }
    if (tabHistory) {
        tabHistory.onclick = renderHistory;
    }
    if (clearBtn) {
        clearBtn.onclick = function() {
            if (window.confirm("确定清空所有历史记录？")) {
                localStorage.removeItem("uploadHistory");
                renderHistory();
            }
        };
    }

    if (exportBtn) {
        exportBtn.onclick = function() {
            var raw = localStorage.getItem("uploadHistory");
            var list = raw ? JSON.parse(raw) : [];
            if (!list.length) {
                alert("无记录");
                return;
            }
            var jsonStr = JSON.stringify(list, null, 2);
            var dataUri = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
            var a = document.createElement("a");
            a.href = dataUri;
            a.download = "history_backup.json";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        };
    }
    
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

    renderHistory();
});
