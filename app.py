"""Novel下载器 — 统一启动器。一键启动前后端，Ctrl+C 优雅关闭。

用法:
    python app.py                  # 默认 0.0.0.0:8000
    python app.py -a 127.0.0.1 -p 8080
"""
import argparse
import os
import shutil
import subprocess
import sys
import signal
import threading
from pathlib import Path

ROOT = Path(__file__).parent


def stream_output(proc: subprocess.Popen, prefix: str):
    """读取子进程输出并逐行打印到 stdout（带前缀）。"""
    for line in proc.stdout:
        print(f"[{prefix}] {line.rstrip()}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Novel下载器 — 统一启动器（前后端）")
    parser.add_argument("-a", "--host", default="0.0.0.0", help="后端绑定地址（默认 0.0.0.0）")
    parser.add_argument("-p", "--port", type=int, default=8000, help="后端端口（默认 8000）")
    args = parser.parse_args()

    print("Novel下载器 启动中...", flush=True)

    # 启动后端 (uvicorn)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", args.host, "--port", str(args.port)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # 查找 npm 完整路径 (Windows 上 subprocess 可能找不到)
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        # 尝试常见安装位置
        candidates = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "nodejs" / "npm.cmd",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "nodejs" / "npm",
        ]
        for c in candidates:
            if c.is_file():
                npm = str(c)
                break
    if not npm:
        print("错误: 找不到 npm，请确认 Node.js 已安装且位于 PATH 中", flush=True)
        sys.exit(1)

    # 启动前端 (Vite dev server)
    frontend = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(ROOT / "frontend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # 后台线程读取并打印输出
    threading.Thread(target=stream_output, args=(backend, "backend"), daemon=True).start()
    threading.Thread(target=stream_output, args=(frontend, "frontend"), daemon=True).start()

    # 注册优雅关闭
    def cleanup(sig, frame):
        print("\n正在关闭...", flush=True)
        for proc, name in [(backend, "backend"), (frontend, "frontend")]:
            try:
                if sys.platform == "win32":
                    # Windows: kill 整个进程树（npm→vite, python→uvicorn）
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    proc.wait(timeout=3)
                else:
                    proc.terminate()
                    proc.wait(timeout=5)
            except Exception:
                proc.kill()
            print(f"[{name}] 已关闭", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 等待任一进程退出
    procs = [backend, frontend]
    while all(p.poll() is None for p in procs):
        try:
            signal.pause()
        except AttributeError:
            import time
            time.sleep(1)


if __name__ == "__main__":
    main()
