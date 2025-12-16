import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import webbrowser
import sys
import socket

# 配置
PORT = 8081
HOST = "127.0.0.1"

app = FastAPI(title="Link Preview Tool")

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>链接代码预览工具 (独立版)</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #10b981; /* 独立版用绿色区分 */
            --bg-color: #f3f4f6;
            --card-bg: #ffffff;
            --text-main: #111827;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --primary-color: #34d399;
                --bg-color: #1f2937;
                --card-bg: #111827;
                --text-main: #f9fafb;
                --text-secondary: #9ca3af;
                --border-color: #374151;
            }
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
            height: 100vh;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
        }

        .header {
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header h1 {
            font-size: 1.5rem;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .header .badge {
            background: var(--primary-color);
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }

        .container {
            flex: 1;
            display: flex;
            gap: 20px;
            height: calc(100vh - 100px);
        }

        .panel {
            flex: 1;
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .panel-header {
            padding: 15px;
            border-bottom: 1px solid var(--border-color);
            font-weight: 600;
            background: rgba(128, 128, 128, 0.05);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        textarea {
            flex: 1;
            width: 100%;
            border: none;
            padding: 15px;
            font-family: 'Consolas', monospace;
            font-size: 14px;
            background: transparent;
            color: var(--text-main);
            resize: none;
            outline: none;
            box-sizing: border-box;
        }

        .preview-area {
            flex: 1;
            padding: 20px;
            overflow: auto;
            background: var(--card-bg);
        }

        .preview-area img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .btn {
            background: var(--primary-color);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: opacity 0.2s;
        }

        .btn:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛠️ 链接代码预览工具 <span class="badge">Standalone</span></h1>
    </div>

    <div class="container">
        <!-- 左侧：输入区 -->
        <div class="panel">
            <div class="panel-header">
                <span>输入代码 (HTML / Markdown)</span>
                <button class="btn" onclick="renderPreview()">渲染预览</button>
            </div>
            <textarea id="inputCode" placeholder="在此粘贴您生成的 HTML 或 Markdown 代码..."></textarea>
        </div>

        <!-- 右侧：预览区 -->
        <div class="panel">
            <div class="panel-header">
                <span>效果预览</span>
            </div>
            <div id="previewArea" class="preview-area">
                <div style="text-align:center;color:var(--text-secondary);margin-top:50px;">
                    请在左侧粘贴代码并点击渲染
                </div>
            </div>
        </div>
    </div>

    <script>
        function renderPreview() {
            var input = document.getElementById('inputCode').value.trim();
            var preview = document.getElementById('previewArea');
            
            if (!input) {
                preview.innerHTML = '<div style="text-align:center;color:var(--text-secondary);margin-top:50px;">请输入代码</div>';
                return;
            }

            var isMarkdown = /^\[.*\]\(.*\)$|^!\[.*\]\(.*\)$/m.test(input) || input.includes('](');

            if (isMarkdown) {
                // Markdown Parser
                var html = input.replace(/\[!\[(.*?)\]\((.*?)\)\]\((.*?)\)/g, '<a href="$3" target="_blank"><img src="$2" alt="$1"></a>');
                html = html.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1">');
                html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
                preview.innerHTML = html;
            } else {
                preview.innerHTML = input;
            }
        }

        document.getElementById('inputCode').addEventListener('input', function() {
            clearTimeout(window.renderTimer);
            window.renderTimer = setTimeout(renderPreview, 500);
        });
    </script>
</body>
</html>
"""

@app.get("/")
def index():
    return HTMLResponse(content=HTML_CONTENT)

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    # check port
    port = PORT
    if is_port_in_use(port):
        print(f"Warning: Port {port} is in use. Trying {port+1}...")
        port += 1
    
    url = f"http://{HOST}:{port}"
    print(f"Starting Preview Tool at {url}")
    print("Press Ctrl+C to stop.")
    
    # Auto open browser
    try:
        webbrowser.open(url)
    except:
        pass

    try:
        uvicorn.run(app, host=HOST, port=port, log_level="warning")
    except KeyboardInterrupt:
        print("Stopped.")
