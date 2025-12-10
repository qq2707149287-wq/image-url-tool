"""
启动入口脚本
使用方法: python run.py
"""
import uvicorn

if __name__ == "__main__":
    # 以模块方式启动，这样相对导入才能正常工作
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
