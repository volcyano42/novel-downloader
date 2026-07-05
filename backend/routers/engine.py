"""Engine 路由 — 5 条。"""
import uuid
from fastapi import APIRouter, HTTPException
from backend.schemas import CreateEngineRequest
from nldlder import create_engine, Options

router = APIRouter(prefix="/api/v1/engine", tags=["engine"])
_instances: dict[str, object] = {}

def _build_options(body: CreateEngineRequest) -> Options:
    opts = Options().set_mode(body.mode)
    if body.mode == "api" and body.api:
        a = body.api
        opts.set_api_options(name=a.name, enabled=a.enabled, delay=a.delay, timeout=a.timeout,
                             retry_times=a.retry_times, batch_size=a.batch_size,
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

@router.get("")
async def list_engines():
    return [{"id": eid, "mode": getattr(eng, "_options", None) and eng._options.mode or "unknown"} for eid, eng in _instances.items()]

@router.post("/create")
async def create(body: CreateEngineRequest):
    engine_id = str(uuid.uuid4())[:8]; opts = _build_options(body)
    _instances[engine_id] = create_engine(opts)
    return {"engine_id": engine_id, "mode": body.mode}

@router.get("/{engine_id}")
async def get_engine(engine_id: str):
    eng = _instances.get(engine_id)
    if not eng: raise HTTPException(404, "引擎不存在")
    opts = getattr(eng, "_options", None)
    return {"id": engine_id, "mode": opts.mode if opts else "unknown"}

@router.delete("/{engine_id}")
async def delete_engine(engine_id: str):
    eng = _instances.pop(engine_id, None)
    if eng and hasattr(eng, "close"): eng.close()
    return {"status": "deleted", "engine_id": engine_id}

@router.get("/type/list")
async def list_engine_types():
    return {"types": ["api", "browser", "requests"]}
