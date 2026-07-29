def _api_url(engine, **params) -> str:
    key = engine.options.key
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    base = f"https://v3.rain.ink/fanqie/?apikey={key}"
    return f"{base}&{qs}" if qs else base
