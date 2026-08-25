# -*- coding: utf-8 -*-
"""番茄正文 frida 代理模式（任意章节）。

原理（2026-08-24 实测打通）：
  1. app（番茄 7.3.3.32）在 x86_64 模拟器上常驻运行（含有效设备会话）；
  2. frida hook okhttp RealInterceptorChain.proceed 把 app 的 reader/full 请求
     改写为目标章节 item_id/book_id（拦截器链正常生成有效的 X-Medusa 等安全头）；
  3. app 请求目标章节 → CryptManager.decrypt（native）解出 gzip 明文 → frida 抓取；
  4. 本模块收集 gzip → 解压 → 返回正文明文 HTML。

前提：模拟器 + frida-server（tcp:27042）+ 番茄 app 已打开过任意正文页（“下一章”
按钮可用）。触发用 adb 点“下一章”（每章一次；章节连续下载时 app 自动翻章，
frida 每次改写为队列中的目标）。
"""
import base64
import gzip
import os
import subprocess
import time

import frida

ADB = os.environ.get("ADB", r"D:/Android/Sdk/platform-tools/adb.exe")
FRIDA_HOST = "127.0.0.1:27042"
AGENT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frida", "frida_agent.js")

BRIDGE_PATH = r"D:/miniconda3/Lib/site-packages/frida_tools/bridges/java.js"


def _bridge_wrapper() -> str:
    raw = open(BRIDGE_PATH, encoding="utf-8").read()
    return "(function () { " + raw + "\nObject.defineProperty(globalThis, 'Java', { value: bridge }); })();\n"


def _restart_frida_server(adb: str = ADB) -> None:
    """重启模拟器内的 frida-server（长时间多会话后 frida-server 会卡死，重启解决）。"""
    for cmd in (
        "killall frida-server 2>/dev/null; sleep 2",
        "nohup /data/local/tmp/frida-server > /dev/null 2>&1 &",
    ):
        subprocess.run([adb, "-s", "emulator-5554", "shell", cmd], capture_output=True, timeout=30)
        time.sleep(1)
    time.sleep(4)
    subprocess.run([adb, "-s", "emulator-5554", "forward", "tcp:27042", "tcp:27042"],
                   capture_output=True, timeout=30)


def _main_pid(adb: str = ADB) -> int:
    """找 app 主进程（PPID=zygote）。"""
    out = subprocess.run([adb, "-s", "emulator-5554", "shell", "ps -A | grep com.dragon.read"],
                         capture_output=True, text=True, timeout=30).stdout
    zygote = None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].startswith("u0_a"):
            zygote = int(parts[1])  # 第一个即主进程（PPID=347）
            break
    return zygote


class FridaChapterClient:
    """连接常驻 app，抓取任意章节正文。"""

    def __init__(self, adb: str = ADB):
        self.adb = adb
        self.dev = frida.get_device_manager().add_remote_device(FRIDA_HOST)
        self.sess = None
        self.script = None
        self._gz = None
        self._events = {}

    def connect(self, timeout: float = 90.0, restart_server: bool = False):
        for attempt in range(3):
            try:
                if restart_server:
                    _restart_frida_server(self.adb)
                pid = _main_pid(self.adb)
                if not pid:
                    raise RuntimeError("未找到 com.dragon.read 主进程（模拟器/app 未运行？）")
                self.sess = self.dev.attach(pid)
                agent = open(AGENT_PATH, encoding="utf-8").read()
                self.script = self.sess.create_script(_bridge_wrapper() + agent)
                ready = {}
                self._events = {}
                self._rewrite_seen = False

                def on_msg(m, d):
                    if m.get("type") != "send":
                        if m.get("type") == "error":
                            self._events["error"] = m
                        return
                    p = m["payload"]
                    if "ready" in p:
                        ready["ok"] = True
                    elif "hooked" in p:
                        ready["hooked"] = True
                    elif "chapter_gzip" in p:
                        self._gz = p["gz_b64"]
                    elif "chapter_target" in p:
                        self._rewrite_seen = True
                    elif "target_ok" in p:
                        ready["target_ok"] = True
                    elif "proxy_err" in p or "ric_err" in p or "cm_err" in p:
                        self._events["hook_err"] = p

                self.script.on("message", on_msg)
                self.script.load()
                t0 = time.time()
                while time.time() - t0 < timeout:
                    if ready.get("hooked"):
                        time.sleep(4.5)  # 等 hook 回调（含 ric_err，~3s 后）
                        if "hook_err" in self._events and "allocate free page" in str(self._events["hook_err"]):
                            raise RuntimeError("frida hook 分配失败（ric_err，跳板页不足）")
                        return
                    time.sleep(1)
                raise RuntimeError("frida hook 未就绪")
            except Exception:
                if attempt == 2:
                    raise
                _restart_frida_server(self.adb)

    def set_target(self, item_id, book_id):
        self._events.pop("target_ok", None)
        self._gz = None
        self._rewrite_seen = False
        self.script.post({"type": "target", "payload": {"item_id": str(item_id), "book_id": str(book_id)}})

    def trigger_next(self, tries: int = 4):
        """adb 点‘下一章’触发 app 发请求（hook 改写为目标章节）。

        模拟器 ARM 转译慢，分开 tap 并长等待（诊断脚本验证过的成功路径）：
        点正文上方关菜单→开菜单→点下一章；直到改写确认或重试耗尽。
        """
        def tap(x, y, wait):
            subprocess.run([self.adb, "-s", "emulator-5554", "shell", f"input tap {x} {y}"],
                           capture_output=True, timeout=150)
            time.sleep(wait)
        for i in range(tries):
            tap("540", "400", 2)
            tap("540", "960", 5)
            tap("961", "1589", 15)
            if self._rewrite_seen:
                return True
        return False

    def wait_gzip(self, timeout: float = 120.0) -> str:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._gz:
                gz = self._gz
                self._gz = None
                return gz
            time.sleep(0.5)
        raise TimeoutError("等待正文明文超时（app 未发 reader/full 请求？）")

    def fetch_chapter(self, item_id, book_id, wait: float = 120.0) -> str:
        """抓取一章正文（返回解压后的 HTML 文本），失败自动重试触发。"""
        last_err = None
        for attempt in range(3):
            self.set_target(item_id, book_id)
            time.sleep(0.5)
            ok = self.trigger_next()
            if not ok:
                last_err = "触发失败（app 未发 reader/full 请求，菜单未唤起？）"
                time.sleep(2)
                continue
            try:
                gz_b64 = self.wait_gzip(wait)
            except TimeoutError as e:
                last_err = str(e)
                time.sleep(2)
                continue
            raw = base64.b64decode(gz_b64)
            return gzip.decompress(raw).decode("utf-8", "replace")
        raise TimeoutError(f"抓取章节超时: {last_err}")


def chapter_content_frida(item_id, book_id, client: FridaChapterClient = None) -> str:
    """便捷入口：给定章节 item_id/book_id 返回正文明文 HTML。"""
    own = client is None
    if own:
        client = FridaChapterClient()
        client.connect()
    try:
        return client.fetch_chapter(item_id, book_id)
    finally:
        if own:
            pass  # 保持连接由调用方管理
