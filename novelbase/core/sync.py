"""多设备同步 — 从对端拉取本地缺失的章节。

设计见 ``docs/superpowers/specs/2026-10-14-terminal-sync-design.md``。

两条硬约束：

1. **对端只读**：全部通过对端既有的 ``/api/v2/storage/*`` GET 接口取数，
   不再新增 ``/sync/*`` 数据面（那是重复造轮子）。
2. **本机写入走进程内**：直接调 storage 层（``save_meta`` / ``save_chapter`` /
   ``set_novel_source``），不走自己的 HTTP。

增量判定的核心是「只补缺」：

- 书级按 ``novel_id``（= ``sha256(url)[:32]``）匹配
- 章节级取远端 ``downloaded`` 的 id 集合，减去本地 ``list_downloaded_ids``
- 两侧都有正文时比 ``(time, count)``；不同则**保留本地**并计入冲突，绝不覆盖
"""
from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from novelbase.models.novel import Chapter, Illustration, Novel

_log = logging.getLogger("novelbase.sync")

# 进度回调：每次读完一段就调一次，参数是扁平 dict（直接可序列化成接口响应）
ProgressCb = Callable[[dict], None] | None

# 每批写入章数：一次事务写多章，减少 SQLite 写锁争用
_BATCH_SIZE = 50


class SyncError(Exception):
    """同步中的可预期错误（连不上对端、对端报错、返回结构异常）。"""


# ── 数据结构 ──────────────────────────────────────

@dataclass
class BookPlan:
    """单本书的同步计划。"""
    novel_id: str
    title: str
    is_new: bool                  # 本地没有这本书
    pull_ids: list[str]           # 待拉取章节 id
    conflicts: int = 0            # 两侧都有但 (time, count) 不同
    source_warn: bool = False     # 来源与本地不一致（仅告警，不阻止同步）


@dataclass
class SyncResult:
    books_added: int = 0
    chapters_pulled: int = 0
    chapters_skipped: int = 0
    conflicts: int = 0
    order_mismatch: list[str] = field(default_factory=list)   # 章节序号不一致 → 跳过整本
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"新增 {self.books_added} 本", f"补 {self.chapters_pulled} 章"]
        if self.chapters_skipped:
            extra = f"（其中 {self.conflicts} 章两侧不同，已保留本地）" if self.conflicts else ""
            parts.append(f"跳过 {self.chapters_skipped} 章{extra}")
        if self.order_mismatch:
            parts.append(f"跳过 {len(self.order_mismatch)} 本（章节序号不一致）")
        if self.errors:
            parts.append(f"{len(self.errors)} 处错误")
        return " · ".join(parts)


# ── 对端客户端 ────────────────────────────────────

class RemoteClient:
    """只读客户端。对端是本项目的另一个实例，接口形状与 storage 一致。"""

    def __init__(self, base_url: str, *, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def __aenter__(self) -> RemoteClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as e:
            raise SyncError(f"连接对端失败（{self.base_url}）：{e}") from e
        if resp.status_code != 200:
            raise SyncError(f"对端返回 {resp.status_code}：{resp.text[:200]}")
        try:
            body = resp.json()
        except ValueError as e:
            raise SyncError(f"对端返回的不是 JSON：{resp.text[:200]}") from e
        # V2ResponseMiddleware 把 /api/v2/* 统一包成 {ok, message, data}
        if isinstance(body, dict) and "ok" in body:
            if not body.get("ok"):
                raise SyncError(str(body.get("message") or "对端返回错误"))
            return body.get("data")
        return body

    async def list_novels(self) -> list[dict]:
        data = await self._get("/api/v2/storage/novel", include_images=False)
        return data or []

    async def get_meta(self, novel_id: str, *, include_images: bool = False) -> dict:
        return await self._get(f"/api/v2/storage/novel/{novel_id}/meta",
                               include_images=include_images)

    async def list_chapters(self, novel_id: str) -> list[dict]:
        # include_content=False：不读正文，只要摘要；size 取接口上限，一次拿完不分页
        data = await self._get(f"/api/v2/storage/novel/{novel_id}/chapters",
                               include_images=False, include_content=False, size=20000)
        return data or []

    async def get_chapter(self, novel_id: str, chapter_id: str, *,
                          include_images: bool = False) -> dict:
        return await self._get(f"/api/v2/storage/novel/{novel_id}/chapter/{chapter_id}",
                               include_images=include_images)


# ── 差集计算（纯函数，便于单测）────────────────────

def diff_chapters(local: dict[str, Chapter],
                  remote: list[dict]) -> tuple[list[str], int]:
    """比对两侧章节摘要 → (待拉取 id 列表, 冲突章数)。

    - 远端没有正文的章节忽略（对端没下完的章拉不到内容）
    - 本地缺失 → 待拉取
    - 两侧都有 → 比 ``(time, count)``；相同则跳过，不同计入冲突并**保留本地**
    """
    pull: list[str] = []
    conflicts = 0
    for rch in remote:
        if not rch.get("downloaded"):
            continue
        cid = rch.get("id")
        if not cid:
            continue
        lch = local.get(cid)
        if lch is None:
            pull.append(cid)
            continue
        if (lch.time, lch.count) != (rch.get("time"), rch.get("count")):
            conflicts += 1
    return pull, conflicts


def order_consistent(local: dict[str, Chapter], remote: list[dict]) -> bool:
    """抽样校验 ``order`` 是否与远端一致（取首/中/末各一条）。

    章节 id 在番茄各书源之间是同一个空间（都是 ``reader/{19位}``），按 id 匹配是安全的；
    但 ``order`` 的算法各源不同（``rain`` 用 enumerate 位置序号、``oiapi`` 用接口 index、
    站点系用 realChapterOrder）。混合填充会让 order 错乱，而 ``oiapi`` 的正文接口是
    **按 order 拉正文**的，错位会导致后续更新拉到错误内容。

    本地查不到对应 id 的章（对端新增章）不参与比较。
    """
    if not remote:
        return True
    picks = {0, len(remote) // 2, len(remote) - 1}
    for i in picks:
        rch = remote[i]
        lch = local.get(rch.get("id") or "")
        if lch is None:
            continue
        if lch.order != rch.get("order") or (lch.title or "") != (rch.get("title") or ""):
            return False
    return True


# ── 远端数据 → 模型 ───────────────────────────────

def _illustration_from_data(img: dict) -> Illustration | None:
    """远端插图 → Illustration；``raw_data`` 为空则跳过。

    不能把 ``raw_data=None`` 传进去：``Illustration.image_format`` 会对 None 调
    ``startswith`` 而崩溃（见 ``novelbase/models/novel.py``）。
    """
    raw = img.get("raw_data")
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            raw = base64.b64decode(raw)
        except (ValueError, TypeError):
            return None
    if not raw:
        return None
    return Illustration(raw_data=raw, alt=img.get("alt"),
                        insert=img.get("insert"), url=img.get("url"))


def chapter_from_data(data: dict) -> Chapter:
    images = tuple(
        ill for ill in (_illustration_from_data(i) for i in (data.get("images") or []))
        if ill is not None
    )
    return Chapter(
        id=data["id"], url=data.get("url", ""), novel_id=data.get("novel_id", ""),
        title=data.get("title", ""), order=data.get("order", 0),
        volume=data.get("volume"), content=data.get("content"),
        time=data.get("time"), count=data.get("count"), images=images,
    )


def novel_from_meta(meta: dict) -> Novel:
    cover = None
    if isinstance(meta.get("cover"), dict):
        cover = _illustration_from_data(meta["cover"])
    return Novel(
        title=meta.get("title") or "", url=meta.get("url") or "",
        serial=meta.get("serial") or 0, author=meta.get("author") or "",
        description=meta.get("description") or "", tags=meta.get("tags"),
        count=meta.get("count"), id=meta.get("id") or "", cover=cover,
    )


# ── 计划构建 ──────────────────────────────────────

async def build_plan(store, client: RemoteClient, *,
                     novel_ids: list[str] | None = None,
                     progress_cb: ProgressCb = None) -> tuple[list[BookPlan], SyncResult]:
    """扫描远端书单并与本地比对，产出待执行的计划。

    返回 (计划列表, 已确定的结果片段)。``order_mismatch`` 在这个阶段就已填好。
    """
    from shared.user_data import get_novel_source

    result = SyncResult()
    remote_novels = await client.list_novels()
    if novel_ids:
        wanted = set(novel_ids)
        remote_novels = [n for n in remote_novels if n.get("id") in wanted]

    plans: list[BookPlan] = []
    total = len(remote_novels)
    for idx, remote_novel in enumerate(remote_novels, start=1):
        novel_id = remote_novel.get("id") or ""
        if not novel_id:
            continue
        title = remote_novel.get("title") or novel_id
        if progress_cb:
            progress_cb({"phase": "scanning", "books_total": total,
                         "books_done": idx - 1, "current_book": title})

        local_meta = store.load_meta(novel_id)
        remote_chapters = await client.list_chapters(novel_id)

        if local_meta is None:
            # 新书：远端已下载的章节全拉
            pull_ids = [c["id"] for c in remote_chapters
                        if c.get("downloaded") and c.get("id")]
            if pull_ids:
                plans.append(BookPlan(novel_id, title, True, pull_ids))
            continue

        local_chapters = {
            ch.id: ch for ch in store.iter_chapters(
                novel_id, include_images=False, include_content=False)
        }

        if not order_consistent(local_chapters, remote_chapters):
            result.order_mismatch.append(title)
            _log.warning("跳过 %s：章节序号与对端不一致", title)
            continue

        pull_ids, conflicts = diff_chapters(local_chapters, remote_chapters)
        result.chapters_skipped += sum(
            1 for c in remote_chapters
            if c.get("downloaded") and c.get("id") in local_chapters
        )
        result.conflicts += conflicts

        source_warn = False
        remote_source = remote_novel.get("source_name")
        if remote_source and get_novel_source(novel_id) not in (None, remote_source):
            source_warn = True
            _log.info("%s 来源不同（本地 %s / 对端 %s），仅告警",
                      title, get_novel_source(novel_id), remote_source)

        if pull_ids:
            plans.append(BookPlan(novel_id, title, False, pull_ids,
                                  conflicts=conflicts, source_warn=source_warn))

    return plans, result


# ── 执行 ──────────────────────────────────────────

async def execute_plan(store, client: RemoteClient, plans: list[BookPlan],
                       result: SyncResult, *, include_images: bool = False,
                       progress_cb: ProgressCb = None,
                       should_stop: Callable[[], bool] | None = None) -> SyncResult:
    """按计划拉取正文并落库（进程内）。

    ``should_stop`` 每章检查一次，返回 True 时中止（已写入的保留，可重跑续传）。
    """
    from shared.user_data import set_novel_source

    total_chapters = sum(len(p.pull_ids) for p in plans)
    done = 0

    for plan in plans:
        novel = store.load_meta(plan.novel_id)
        if novel is None:
            # 新书：先建库。必须用 /meta（列表里的 cover 是缩略图且无 extra）
            meta = await client.get_meta(plan.novel_id, include_images=include_images)
            novel = novel_from_meta(meta)
            if not novel.id:
                novel.id = plan.novel_id
            store.save_meta(novel)
            result.books_added += 1
            source = meta.get("source_name")
            if source:
                try:
                    set_novel_source(plan.novel_id, source)
                except Exception as e:      # noqa: BLE001 — 来源写不进去不应中断同步
                    _log.warning("写入来源失败 %s: %s", plan.novel_id, e)

        batch: list[Chapter] = []
        for cid in plan.pull_ids:
            if should_stop and should_stop():
                _log.info("同步被中止，已写入的章节保留")
                return result
            data = await client.get_chapter(plan.novel_id, cid,
                                            include_images=include_images)
            batch.append(chapter_from_data(data))
            done += 1
            if len(batch) >= _BATCH_SIZE:
                store.save_chapter(novel, batch)
                result.chapters_pulled += len(batch)
                batch = []
                if progress_cb:
                    progress_cb({"phase": "pulling", "books_total": len(plans),
                                 "chapters_total": total_chapters, "chapters_done": done,
                                 "current_book": plan.title,
                                 "current_chapter": data.get("title") or ""})
        if batch:
            store.save_chapter(novel, batch)
            result.chapters_pulled += len(batch)
            if progress_cb:
                progress_cb({"phase": "pulling", "books_total": len(plans),
                             "chapters_total": total_chapters, "chapters_done": done,
                             "current_book": plan.title,
                             "current_chapter": ""})

    return result


async def sync_from(store, peer_url: str, *,
                    novel_ids: list[str] | None = None,
                    include_images: bool = False,
                    progress_cb: ProgressCb = None,
                    should_stop: Callable[[], bool] | None = None) -> SyncResult:
    """完整流程：扫描 → 建计划 → 拉取落库。"""
    async with RemoteClient(peer_url) as client:
        if progress_cb:
            progress_cb({"phase": "scanning", "books_total": 0, "books_done": 0,
                         "current_book": ""})
        plans, result = await build_plan(store, client, novel_ids=novel_ids,
                                         progress_cb=progress_cb)
        _log.info("同步计划：%d 本待处理（跳过 %d 章已有）", len(plans), result.chapters_skipped)
        result = await execute_plan(store, client, plans, result,
                                    include_images=include_images,
                                    progress_cb=progress_cb,
                                    should_stop=should_stop)
    if progress_cb:
        progress_cb({"phase": "done", "summary": result.summary()})
    return result
