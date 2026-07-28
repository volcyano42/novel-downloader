import time

from novelbase.models.auth import AuthCredential


def login(engine, **kwargs) -> AuthCredential:
    page = engine.new_page()

    try:
        page.get("https://fanqienovel.com/")

        print("请在打开的浏览器窗口中完成登录（扫码/手机号）...")
        deadline = time.time() + 120
        while time.time() < deadline:
            if "author" in page.url:
                break
            time.sleep(0.5)

        time.sleep(2)

        raw_cookies = page.cookies()
        cookies = {c["name"]: c["value"] for c in raw_cookies}

        headers = {}

        return AuthCredential(
            cookies=cookies,
            headers=headers,
            extra={}
        )
    finally:
        page.close()
