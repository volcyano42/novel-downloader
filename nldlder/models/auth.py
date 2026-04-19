from dataclasses import dataclass, field

@dataclass
class AuthCredential:
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    token: str | None = None
    extra: dict = field(default_factory=dict)

    def apply_to_requests_engine(self, engine):
        """将认证信息应用到 RequestsEngine"""
        if self.cookies:
            engine.session.cookies.update(self.cookies)
        if self.headers:
            engine.session.headers.update(self.headers)

    def apply_to_browser_context(self, context):
        """将认证信息应用到 Playwright 的 BrowserContext"""
        if self.cookies:
            context.add_cookies([
                {'name': k, 'value': v, 'url': self.extra.get('base_url', '')}
                for k, v in self.cookies.items()
            ])
        if self.headers:
            context.set_extra_http_headers(self.headers)