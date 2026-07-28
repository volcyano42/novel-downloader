from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthCredential:
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    token: str | None = None
    extra: dict = field(default_factory=dict)

    def apply_to_requests_engine(self, engine: Any) -> None:
        """将认证信息应用到 RequestsEngine。"""
        if self.cookies:
            engine.session.cookies.update(self.cookies)
        if self.headers:
            engine.session.headers.update(self.headers)

    def apply_to_browser_page(self, page: Any) -> None:
        """将认证信息应用到 DrissionPage 的 ChromiumPage / ChromiumTab。

        Cookies 通过 ``page.set.cookies()`` 注入；
        headers 需在创建 engine 时通过 ``ChromiumOptions`` 设置，
        此处无法动态覆盖。
        """
        if self.cookies:
            page.set.cookies([
                {'name': k, 'value': v}
                for k, v in self.cookies.items()
            ])