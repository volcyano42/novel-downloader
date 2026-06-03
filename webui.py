"""
novel-downloader Web UI 入口
────────────────────────────
FastAPI + SSE 进度推送

启动:  python webui.py
"""
from service import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webui:app", host="127.0.0.1", port=8000, reload=True)
