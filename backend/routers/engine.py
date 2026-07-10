"""Engine 路由 — 6 条。"""
import uuid
from fastapi import APIRouter, HTTPException
from backend.schemas import CreateEngineRequest, UpdateEngineRequest
from nldlder import create_engine, Options

router = APIRouter(prefix="/api/v1/engine", tags=["engine"])
_instances: dict[str, dict] = {}

def _build_options(body: CreateEngineRequest | UpdateEngineRequest) -> Options:
    opts = Options().set_mode(body.mode)
    if body.mode == "api" and body.api:
        a = body.api
        opts.set_api_options(name=a.name, enabled=a.enabled, delay=a.delay, timeout=a.timeout,
                             retry_times=a.retry_times,
                             backoff_factor=a.backoff_factor, key=a.key, params=a.params)
    elif body.mode == "requests" and body.requests:
        r = body.requests
        opts.set_requests_options(headers=r.headers, delay=r.delay, timeout=r.timeout,
                                  retry_times=r.retry_times, backoff_factor=r.backoff_factor,
                                  cookies=r.cookies, proxies=r.proxies)
    elif body.mode == "browser" and body.browser:
        b = body.browser
        opts.set_browser_options(browser_type=b.browser_type, delay=b.delay, timeout=b.timeout,
                                 retry_times=b.retry_times, backoff_factor=b.backoff_factor,
                                 headless=b.headless, user_data_dir=b.user_data_dir, viewport=b.viewport)
    return opts


def _get_sub_options(body: CreateEngineRequest | UpdateEngineRequest):
    """从请求体构建子选项对象（用于 update_options）。"""
    from nldlder.core.options import APIOptions, RequestsOptions, BrowserOptions

    if body.mode == "api" and body.api:
        a = body.api
        return APIOptions(name=a.name, enabled=a.enabled, delay=a.delay, timeout=a.timeout,
                          retry_times=a.retry_times, backoff_factor=a.backoff_factor,
                          key=a.key, params=a.params)
    elif body.mode == "requests" and body.requests:
        r = body.requests
        return RequestsOptions(headers=r.headers, delay=r.delay, timeout=r.timeout,
                               retry_times=r.retry_times, backoff_factor=r.backoff_factor,
                               cookies=r.cookies, proxies=r.proxies)
    elif body.mode == "browser" and body.browser:
        b = body.browser
        return BrowserOptions(browser_type=b.browser_type, delay=b.delay, timeout=b.timeout,
                              retry_times=b.retry_times, backoff_factor=b.backoff_factor,
                              headless=b.headless, user_data_dir=b.user_data_dir,
                              viewport=b.viewport)
    return None


@router.get("")
async def list_engines():
    return [
        {"id": eid, "mode": info["mode"], "platform": info.get("platform", "")}
        for eid, info in _instances.items()
    ]


@router.post("/create")
async def create(body: CreateEngineRequest):
    engine_id = str(uuid.uuid4())[:8]
    opts = _build_options(body)
    engine = create_engine(opts)
    _instances[engine_id] = {"engine": engine, "platform": body.platform, "mode": body.mode}
    return {"engine_id": engine_id, "mode": body.mode, "platform": body.platform}


@router.get("/{engine_id}")
async def get_engine(engine_id: str):
    info = _instances.get(engine_id)
    if not info:
        raise HTTPException(404, "引擎不存在")
    return {"id": engine_id, "mode": info["mode"], "platform": info.get("platform", "")}


@router.put("/{engine_id}")
async def update_engine(engine_id: str, body: UpdateEngineRequest):
    info = _instances.get(engine_id)
    if not info:
        raise HTTPException(404, "引擎不存在")

    engine = info["engine"]
    sub_opts = _get_sub_options(body)
    if sub_opts is None:
        raise HTTPException(400, f"无效的 mode 或缺少对应选项: {body.mode}")

    engine.update_options(sub_opts)
    info["mode"] = body.mode
    return {"id": engine_id, "mode": body.mode, "platform": info.get("platform", "")}


@router.delete("/{engine_id}")
async def delete_engine(engine_id: str):
    info = _instances.pop(engine_id, None)
    if info:
        eng = info["engine"]
        if hasattr(eng, "close"):
            eng.close()
    return {"status": "deleted", "engine_id": engine_id}


@router.get("/type/list")
async def list_engine_types():
    return {"types": ["api", "browser", "requests"]}
