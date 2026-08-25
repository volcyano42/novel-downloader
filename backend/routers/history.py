"""搜索历史路由 — /api/v2/history 按天分组的搜索历史读写删除。"""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v2/history", tags=["history"])


class SearchHistoryAddRequest(BaseModel):
    platform: str = ""
    keyword: str
    mode: str = ""
    variant: str = ""


def _date_label(d: date) -> str:
    today = date.today()
    if d == today:
        return "今天"
    if (today - d).days == 1:
        return "昨天"
    if d.year == today.year:
        return f"{d.month}月{d.day}日"
    return f"{d.year}年{d.month}月{d.day}日"


@router.get("/search")
async def get_search_history(limit: int = 50):
    from shared.user_data import get_search_history as _get

    rows = _get(limit=min(max(limit, 1), 200))
    grouped: list[dict] = []
    current: dict | None = None
    for row in rows:
        searched_at = row.get("searched_at") or ""
        try:
            day = datetime.strptime(searched_at[:10], "%Y-%m-%d").date()
        except ValueError:
            day = date.today()
        label = _date_label(day)
        if current is None or current["date_label"] != label:
            current = {"date_label": label, "items": []}
            grouped.append(current)
        current["items"].append({
            "id": row["id"],
            "platform": row.get("platform") or "",
            "mode": row.get("mode") or "",
            "variant": row.get("variant") or "",
            "keyword": row.get("keyword") or "",
            "searched_at": searched_at,
        })
    return {"history": grouped}


@router.post("/search")
async def add_search_history(body: SearchHistoryAddRequest):
    keyword = body.keyword.strip()
    if not keyword:
        raise HTTPException(400, "搜索关键词不能为空")
    from shared.user_data import add_search_history as _add

    _add(body.platform, keyword, body.mode, body.variant)
    return {"status": "ok"}


@router.delete("/search/{history_id}")
async def delete_search_history(history_id: int):
    from shared.user_data import delete_search_history as _delete

    ok = _delete(history_id)
    if not ok:
        raise HTTPException(404, "搜索历史不存在")
    return {"status": "ok"}
