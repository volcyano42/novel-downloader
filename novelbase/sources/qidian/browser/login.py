"""起点 browser 模式 - 登录。"""
import time

from novelbase.core.engine import BrowserEngine
from novelbase.models.auth import AuthCredential
from novelbase.utils.logger import get_logger

_log = get_logger("novelbase.fetchers.qidian")


def login(engine: BrowserEngine, **kwargs) -> AuthCredential:
    _log.info("login start")
    page = engine.new_page()
    try:
        page.get("https://passport.qidian.com/")
        print("请在打开的浏览器窗口中完成登录（扫码/手机号）...")
        deadline = time.time() + 120
        while time.time() < deadline:
            if "www.qidian.com" in page.url:
                break
            time.sleep(0.5)
        time.sleep(2)
        _log.info("login completed")
        raw_cookies = page.cookies()
        cookies = {c["name"]: c["value"] for c in raw_cookies}
        return AuthCredential(cookies=cookies, headers={}, extra={})
    finally:
        page.close()
