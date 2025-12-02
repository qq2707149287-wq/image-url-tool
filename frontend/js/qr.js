"use strict";

const QrManager = (function () {
    let qrModalElement = null;
    let qrContainerElement = null;
    let qrTitleElement = null;
    let qrInstance = null;

    function createQrModalIfNeeded() {
        if (qrModalElement) {
            return;
        }
        qrModalElement = document.createElement("div");
        qrModalElement.className = "qr-backdrop";
        qrModalElement.innerHTML =
            "<div class=\"qr-modal\">" +
            "<div class=\"qr-header\">" +
            "<span id=\"qrTitle\"></span>" +
            "<button type=\"button\" id=\"qrCloseBtn\" class=\"qr-close-btn\">×</button>" +
            "</div>" +
            "<div id=\"qrCodeContainer\" class=\"qr-body\"></div>" +
            "</div>";
        document.body.appendChild(qrModalElement);
        qrTitleElement = document.getElementById("qrTitle");
        qrContainerElement = document.getElementById("qrCodeContainer");
        var closeBtn = document.getElementById("qrCloseBtn");
        if (closeBtn) {
            closeBtn.onclick = hideQrModal;
        }
        qrModalElement.onclick = function (e) {
            if (e.target === qrModalElement) {
                hideQrModal();
            }
        };
    }

    function hideQrModal() {
        if (qrModalElement) {
            qrModalElement.style.display = "none";
        }
    }

    function showQrForUrl(url, title) {
        if (!url) {
            if (typeof showToast === 'function') {
                showToast("没有可生成二维码的链接", "warning");
            } else {
                console.warn("showToast function not found");
                alert("没有可生成二维码的链接");
            }
            return;
        }
        createQrModalIfNeeded();
        if (qrTitleElement) {
            qrTitleElement.textContent = title || "图片链接二维码";
        }
        if (qrContainerElement) {
            qrContainerElement.innerHTML = "";
            if (typeof QRCode === "function") {
                qrInstance = new QRCode(qrContainerElement, {
                    text: url,
                    width: 200,
                    height: 200,
                    correctLevel: QRCode.CorrectLevel.M
                });
            } else {
                qrContainerElement.textContent = url;
            }
        }
        if (qrModalElement) {
            qrModalElement.style.display = "flex";
        }
    }

    return {
        showQrForUrl: showQrForUrl
    };
})();

// Expose to global scope for backward compatibility
window.showQrForUrl = QrManager.showQrForUrl;
