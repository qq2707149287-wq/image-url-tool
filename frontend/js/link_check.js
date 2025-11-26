"use strict";

var autoCheckTimer = null;
var checkQueue = [];
var isChecking = false;

// 更新单条记录的状态
function setHistoryRecordStatusByUrl(url, status) {
    if (typeof ensureHistoryArray === 'function') ensureHistoryArray();
    else if (!Array.isArray(uploadHistory)) uploadHistory = [];

    var changed = false;
    for (var i = 0; i < uploadHistory.length; i++) {
        var r = uploadHistory[i];
        if (r && r.url === url) {
            // 只在状态真的改变时才保存
            if (r.linkStatus !== status) {
                r.linkStatus = status;
                changed = true;
            }
            break;
        }
    }
    if (changed) {
        try {
            localStorage.setItem("imageUploadHistory", JSON.stringify(uploadHistory));
        } catch (e) { }
    }
    return changed;
}

// 原地更新 DOM (如果不刷新列表)
function updateHistoryDomVisuals(url, status) {
    var items = document.querySelectorAll("#historyList .history-item");
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        if (item.getAttribute("data-url") === url) {
            // 找到标题行
            var strong = item.querySelector(".history-info strong");
            if (!strong) continue;

            // 移除旧的警告图标（如果有）
            var existingWarn = strong.querySelector("span[title='此链接可能已失效']");
            if (existingWarn) strong.removeChild(existingWarn);

            // 如果是 bad，添加图标
            if (status === "bad") {
                var warnSpan = document.createElement("span");
                warnSpan.textContent = " ⚠️";
                warnSpan.title = "此链接可能已失效";
                warnSpan.style.cursor = "help";
                warnSpan.style.fontSize = "1.1em";
                strong.appendChild(warnSpan);
            }
            break;
        }
    }
}

// 实际执行检测的函数
function checkSingleUrl(url) {
    return fetch("/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            var status = "unknown";
            if (result.data && result.data.success) {
                status = "ok";
            } else {
                var kind = result.data ? result.data.kind : "error";
                if (kind === "invalid") status = "bad";
                else status = "unknown";
            }
            // 更新数据和UI
            var changed = setHistoryRecordStatusByUrl(url, status);
            if (changed) {
                updateHistoryDomVisuals(url, status);
            }
            return status;
        })
        .catch(function () {
            // 网络错误算 unknown，不贸然判死刑
            setHistoryRecordStatusByUrl(url, "unknown");
        });
}

// 队列处理器
function processQueue() {
    if (checkQueue.length === 0) {
        isChecking = false;
        return;
    }

    isChecking = true;
    var url = checkQueue.shift(); // 取出第一个

    checkSingleUrl(url).finally(function () {
        // 间隔 200ms 处理下一个，避免请求风暴
        setTimeout(processQueue, 200);
    });
}

// 对外暴露的触发器 (带防抖)
function triggerAutoCheck() {
    if (autoCheckTimer) clearTimeout(autoCheckTimer);
    autoCheckTimer = setTimeout(runAutoCheck, 500); // 列表渲染完 0.5s 后启动
}

function runAutoCheck() {
    if (typeof uploadHistory === "undefined") return;
    
    // 1. 找出所有状态未知 (null 或 unknown) 的 URL
    // 只检查当前列表里显示出来的（比如搜素过滤后的），或者检查全部？
    // 为了体验，建议检查全部数据中状态未知的。
    
    var pendingUrls = [];
    for (var i = 0; i < uploadHistory.length; i++) {
        var r = uploadHistory[i];
        // 只检测未检测过的，或者上次检测结果不明的
        // 已经 ok 或 bad 的就不重复检测了，节省资源
        if (!r.linkStatus || r.linkStatus === "unknown") {
            // 去重防止队列重复
            if (checkQueue.indexOf(r.url) === -1) {
                pendingUrls.push(r.url);
            }
        }
    }

    if (pendingUrls.length === 0) return;

    // 加入队列
    checkQueue = checkQueue.concat(pendingUrls);

    // 如果没在运行，就启动运行
    if (!isChecking) {
        processQueue();
    }
}
