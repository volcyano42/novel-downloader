"""下载任务管理器 — asyncio 原生、暂停/恢复、进度跟踪、真正取消。

create_task/list_tasks/pause_task/resume_task/delete_task 保持同步 def，
由 FastAPI async 路由在事件循环线程里调用；下载协程通过
asyncio.get_running_loop() + loop.create_task 调度到同一事件循环。

并发模型（2026-09-25 重做，见 docs/superpowers/specs/2026-09-25-download-concurrency-design.md）：
- **任务级额度**：同时运行的下载任务数上限 = `download.max_workers`（默认 3），
  超额任务停在 `queued`，拿到额度才转 `downloading`。
- **书源级额度**：同一书源同时最多 `source_concurrency(source)` 个请求在飞，
  **跨任务共享**（默认 1）。

两者都用**轮询式计数**而非固定容量 asyncio.Semaphore：`max_workers` 与书源
`concurrency` 都是运行时可改配置（UI 改完立即生效），轮询式能立刻反映新上限
（与 `_wait_if_paused` 的轮询风格一致）。
"""
import asyncio
import logging
import threading
import time
import uuid

from backend.services.engine_manager import get_cached_engine
from novelbase.core.exceptions import ChapterNotFoundError
from shared.config import load_config, get_database_url, source_concurrency
from shared.user_data import set_novel_source

_log = logging.getLogger("backend.task_manager")

_tasks: dict[str, dict] = {}
# 单事件循环下协程之间不会在同步语句上交错，但下载协程与 create_task/
# list_tasks 等同步函数混用时，threading.Lock 仍是最稳妥的保护（等价的
# asyncio.Lock 无法在同步函数里 acquire）。任务槽与书源额度计数共用此锁。
_tasks_lock = threading.Lock()

# 当前持有任务级额度的 task_id 集合（同时运行的任务数上限 = max_workers）。
_running_tasks: set[str] = set()
# 各书源当前在飞的请求数（跨任务共享，上限 = source_concurrency(source)）。
_source_active: dict[str, int] = {}
# 各书源「额度释放」唤醒队列：等额度的协程在此登记 Future，`_release_source_slot`
# 释放后 set_result 立即唤醒（事件驱动，取代定时轮询）。绑定当前事件循环，跨 loop
# （如测试里多次 asyncio.run）复用时重置，避免 Future 串 loop。
_source_waiters: dict[str, list[asyncio.Future]] = {}
_source_waiters_loop: asyncio.AbstractEventLoop | None = None

_QUEUE_POLL_INTERVAL = 0.2
# 等书源额度改「释放即唤醒」：释放后立即唤醒等待者，避免定时/退避轮询在「单请求耗时
# < 检查间隔」时空转（默认 concurrency=1 会退化成 ~2 章/s）。空闲期用有界超时兜底，
# 兼顾暂停/取消感知（超时后重查 _cancel/_pause）。
_SOURCE_WAIT_TIMEOUT = 0.2
# 章节分批提交：把「同时挂起、等书源额度」的协程数从全部章节压到每批 _BATCH_SIZE，
# 批间串行；批内仍受书源额度约束。避免千章书一次性挂起 N 个协程的无谓开销。
_BATCH_SIZE = 32
_MAX_WORKERS_TTL = 1.0
# (time.monotonic() 时间戳, max_workers) —— 短 TTL 缓存，避免排队轮询每 0.2s 读 config.yaml
_max_workers_cache: tuple[float, int] | None = None


def _max_workers() -> int:
    """运行时可改的任务并发上限（`download.max_workers`，非法值回退出厂默认 3）。

    带 `_MAX_WORKERS_TTL`（1s）TTL 缓存：排队轮询每 `_QUEUE_POLL_INTERVAL` 判断一次
    上限，不必每次都读 config.yaml；改配置后最多 1s 生效。
    """
    global _max_workers_cache
    now = time.monotonic()
    cached = _max_workers_cache
    if cached is not None and now - cached[0] < _MAX_WORKERS_TTL:
        return cached[1]
    value = _read_max_workers()
    _max_workers_cache = (now, value)
    return value


def _read_max_workers() -> int:
    """安全读取 `download.max_workers`，任何非法/异常值一律回退出厂默认 3。

    调用点 `_acquire_task_slot` 位于 `_run_download` 的 try 之外：若这里把异常抛出去
    （例如 config.yaml 被手改成非数字 → `int(...)` 抛 TypeError），异常会逃逸到事件循环，
    任务永久停在 `queued`。故对结构异常（download 非 dict）与类型异常一并兜住，绝不外抛。
    """
    try:
        return max(1, int(load_config().get("download", {}).get("max_workers", 3)))
    except (TypeError, ValueError, AttributeError):
        _log.warning("download.max_workers 非法，回退 3", exc_info=True)
        return 3


async def _acquire_task_slot(task: dict) -> bool:
    """轮询等待任务级额度：拿到返回 True，被取消返回 False。

    轮询而非固定容量 asyncio.Semaphore：`max_workers` 是运行时可改配置（带 1s TTL
    缓存），轮询能反映新上限。等额度期间任务保持 `queued`，且响应取消。

    **排队中暂停不抢任务槽**：`_pause` 置位时不入槽（保持 `queued`），继续轮询等待
    `resume` —— 否则 `max_workers=1` 时被暂停的排队任务会占住唯一的槽、把队列堵死。
    取消仍立即退出（不留 `downloading` 残影）。
    """
    while True:
        if task["_cancel"].is_set():
            return False
        if task["_pause"].is_set():
            # 排队中暂停：不占任务槽（不阻塞队列），保持 queued 等 resume
            with _tasks_lock:
                task["status"] = "queued"
            await asyncio.sleep(_QUEUE_POLL_INTERVAL)
            continue
        max_workers = _max_workers()   # 锁外读配置（含文件 IO），避免持锁做 IO
        with _tasks_lock:
            if task["task_id"] in _running_tasks:
                return True
            if len(_running_tasks) < max_workers:
                _running_tasks.add(task["task_id"])
                return True
        await asyncio.sleep(_QUEUE_POLL_INTERVAL)


def _release_task_slot(task: dict) -> None:
    with _tasks_lock:
        _running_tasks.discard(task["task_id"])


def _source_waiters_for(source_name: str) -> list[asyncio.Future]:
    """取该书源的等待者列表（惰性创建，绑定当前事件循环）。

    跨 loop 复用时清空旧 Future，避免把唤醒投递到已关闭的循环。
    """
    global _source_waiters_loop
    loop = asyncio.get_running_loop()
    if _source_waiters_loop is not loop:
        _source_waiters.clear()
        _source_waiters_loop = loop
    return _source_waiters.setdefault(source_name, [])


def _discard_waiter(waiters: list[asyncio.Future], fut: asyncio.Future) -> None:
    """把 fut 从等待者列表移除（可能已被 `_wake_source_waiters` clear，忽略缺失）。"""
    try:
        waiters.remove(fut)
    except ValueError:
        pass


def _handoff_source_slot(source_name: str) -> bool:
    """把刚释放的额度**直接交接**给等待队列的队首（严格 FIFO），返回是否交接成功。

    交接方式：给队首的 Future `set_result(True)`（=「额度已归你」），**不把它移出队列**，
    由接手的协程自己出队。因此「谁接手」由登记先后唯一决定，与协程唤醒顺序无关。

    历史实现（2026-09-30 前）是「唤醒全部等待者 + 清空队列、各自重查额度竞争接手」：
    配合 `_SOURCE_WAIT_TIMEOUT` 超时兜底（每个超时者出队后重新 append 到队尾），接手
    顺序被随机化 → 下载顺序不再等于章节顺序（并发 1、严格串行时也会乱）。
    """
    waiters = _source_waiters.get(source_name)
    if not waiters:
        return False
    for fut in waiters:
        if not fut.done():
            fut.set_result(True)
            return True
    return False


async def _acquire_source_slot(source_name: str, task: dict, limit: int) -> bool:
    """等待书源级额度（跨任务共享）：拿到返回 True，任务被取消返回 False。

    **严格 FIFO**：队列无人且额度可用时直接拿（无等待者时零开销）；否则登记 Future
    排队，额度由 `_release_source_slot` 交接给队首 —— 接手顺序恒等于登记顺序（= 章节
    顺序），不受 `_SOURCE_WAIT_TIMEOUT` 超时影响（超时只为感知取消/暂停，Future 与其
    队列位置都保留）。

    `limit` 由调用方在任务开始时取一次并缓存（`source_concurrency()` 会读
    `sites/*.yaml` 与 `source.json`，不得进每请求热路径）。等待期间若任务被暂停，
    则不占额度地停在 `paused`（优雅暂停：未开始的请求停住，已在飞的请求跑完）。
    """
    limit = max(1, limit)
    loop = asyncio.get_running_loop()
    waiters = _source_waiters_for(source_name)
    fut = loop.create_future()
    queued = False    # 当前 Future 是否还在等待队列里
    handed = False    # 额度所有权是否已交给调用方（由调用方的 finally 释放）
    try:
        while True:
            if task["_cancel"].is_set():
                return False
            if task["_pause"].is_set():
                # 排队中暂停：不占额度（已接手的先归还）、让出队列位置，resume 后重排
                if queued:
                    _discard_waiter(waiters, fut)
                    queued = False
                if _is_slot_handoff(fut):
                    _release_source_slot(source_name)   # 刚接手就暂停 → 归还，不占额度
                fut = loop.create_future()
                with _tasks_lock:
                    task["status"] = "paused"
                await asyncio.sleep(0.1)
                continue
            if queued and fut.done():
                if _is_slot_handoff(fut):
                    # 被交接：额度已归本协程，交给调用方释放
                    handed = True
                    return True
                _discard_waiter(waiters, fut)   # 防御：非交接完成 → 出队重排
                queued = False
                fut = loop.create_future()
            with _tasks_lock:
                if not queued:
                    # 快路径：队列无人等待且额度可用 → 直接拿
                    if not any(not f.done() for f in waiters) \
                            and _source_active.get(source_name, 0) < limit:
                        _source_active[source_name] = \
                            _source_active.get(source_name, 0) + 1
                        return True
                    waiters.append(fut)
                    queued = True
                    # 登记后复检：额度可能恰在「检查」与「登记」之间被释放（交接落空）
                    if waiters[0] is fut and _source_active.get(source_name, 0) < limit:
                        _source_active[source_name] = \
                            _source_active.get(source_name, 0) + 1
                        _discard_waiter(waiters, fut)
                        queued = False
                        return True
            try:
                # shield：超时只结束本次等待，fut 与其队列位置都保留（顺序不被打乱）
                await asyncio.wait_for(asyncio.shield(fut), _SOURCE_WAIT_TIMEOUT)
            except asyncio.TimeoutError:
                pass
    finally:
        if queued:
            _discard_waiter(waiters, fut)
        if not handed and _is_slot_handoff(fut):
            # 已接手但没能交给调用方（被取消 / 异常 / 上层未及释放）→ 归还，防额度泄漏
            _release_source_slot(source_name)


def _is_slot_handoff(fut) -> bool:
    """该 Future 是否已被交接额度（`done` 且 result 为 `True`；防御 `cancelled`）。"""
    return fut.done() and not fut.cancelled() and fut.result() is True


def _release_source_slot(source_name: str) -> None:
    """释放书源额度：**有等待者时交接给队首**（占用数不变，所有权转移），否则递减。

    下界保护：计数已为 0 时说明出现了双释放 / 漏 acquire（额度泄漏会让该源永久
    卡死），记录 error 而非静默 `pop`，使其在日志中暴露。
    """
    with _tasks_lock:
        active = _source_active.get(source_name, 0)
        if active <= 0:
            _log.error("书源额度释放不匹配（重复释放/漏 acquire）: %s", source_name)
            active = 0
        queued = any(not f.done() for f in _source_waiters.get(source_name) or [])
        if queued:
            # 交接：原持有者退出、队首接手 → 占用数不变（不经过「空闲」窗口，避免插队）
            _source_active[source_name] = active
        else:
            n = active - 1
            if n > 0:
                _source_active[source_name] = n
            else:
                _source_active.pop(source_name, None)
    if queued:
        _handoff_source_slot(source_name)


async def _run_download(task: dict, source_name: str):
    """下载协程入口：先排任务级额度（超额停在 queued），再执行下载主体。"""
    # ── 任务级排队：超额任务停在 queued，直到拿到额度（轮询，响应取消/暂停）──
    if not await _acquire_task_slot(task):
        # 排队中被取消：立即退出，不留 downloading 残影
        return
    try:
        with _tasks_lock:
            # acquire 返回 True 时必未暂停（入槽与暂停检查在同一同步段，无 await），
            # 故直接转 downloading
            if task["_cancel"].is_set():
                return
            task["status"] = "downloading"
        await _run_download_impl(task, source_name)
    finally:
        # 任务结束（无论成败/取消）必须释放任务槽
        _release_task_slot(task)


async def _run_download_impl(task: dict, source_name: str):
    """下载主体：按书源取引擎 → 并发下载章节 → 收尾状态，支持暂停/取消。"""
    from novelbase import resolve_meta, resolve_chapter
    from novelbase.models.novel import Chapter, Chapters, Novel
    from novelbase.core.storage import create_storage
    from novelbase.core.options import StorageOptions
    from shared.config import effective_capabilities

    # 书源并发额度：任务开始时取一次并缓存进闭包（`source_concurrency()` 会读
    # sites/*.yaml 与 source.json，无缓存，不得进每请求/每章热路径）。该任务发出的
    # 所有请求（meta + 每章）共用这一额度。
    src_conc = max(1, source_concurrency(source_name))

    # engines(mode)->engine 解析器：按书源能力声明的 mode 惰性取引擎。
    # get_cached_engine(source_name, mode) 带缓存，命中即复用同一实例。
    engines_cache: dict[str, object] = {}

    def engines(m: str):
        if m not in engines_cache:
            engines_cache[m] = get_cached_engine(source_name, m)
        return engines_cache[m]

    # 主 mode 预热：get_cached_engine 是同步调用，browser 模式首次创建会启动
    # Chromium，若首次创建落在事件循环线程会阻塞整个 FastAPI（含其它任务、
    # 暂停/取消接口）数秒。resolve_meta/resolve_chapter 在事件循环里同步求值
    # engines(mode)，故先用 to_thread 把「该源 novel_info 能力声明的 mode」
    # （即解析将首先用到的 mode）建到缓存，移出事件循环线程。
    _caps = effective_capabilities(source_name)
    primary_mode = _caps.get("novel_info") or next(iter(_caps.values()), None)
    if primary_mode:
        engines_cache[primary_mode] = await asyncio.to_thread(
            get_cached_engine, source_name, primary_mode)

    try:
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))

        novel_url = task.get("novel_url", "")
        if novel_url:
            # 元数据请求也占书源额度：该任务发出的所有请求都受同一书源上限约束
            if not await _acquire_source_slot(source_name, task, src_conc):
                return
            try:
                meta = await resolve_meta(novel_url, source_name, engines,
                                          mode_overrides=_caps)
                store.save_meta(meta)
            except Exception:
                _log.warning("fetch_meta failed for %s", novel_url, exc_info=True)
            finally:
                _release_source_slot(source_name)

        # 来源由调用方显式给出，不依赖 meta 是否取到：即使 fetch_meta 失败也要记录，
        # 否则该书在后续「更新」时会被当成未知来源而跳过。
        try:
            set_novel_source(task["novel_id"], source_name)
        except Exception:
            _log.warning("set_novel_source failed for %s", task.get("novel_id"), exc_info=True)

        novel = Novel(title=task["title"], url=novel_url, id=task["novel_id"],
                      serial=0, author="", description="")

        _eta_samples: list[float] = []
        _eta_lock = threading.Lock()

        def _update_eta(elapsed: float):
            with _eta_lock:
                _eta_samples.append(elapsed)
                if len(_eta_samples) > 10:
                    _eta_samples.pop(0)
                avg = sum(_eta_samples) / len(_eta_samples)
                remaining = task["total"] - task["progress"]
                # 章节并发度 = 书源并发额度（任务开始时缓存进闭包，跨任务共享，
                # 仅为近似估算）；不再与 max_workers 挂钩。
                eta_seconds = avg * remaining / src_conc
                with _tasks_lock:
                    task["eta"] = eta_seconds

        async def _wait_if_paused() -> bool:
            """暂停/取消检查点：暂停中轮询等 resume（clear），取消返回 False。

            优雅暂停语义：当前下载中的章节跑完后、下一章开始前停住。
            asyncio.Event 无「等待 clear」方法，用轮询实现（原 await
            _pause.wait() 在 event 已 set 时立即返回，暂停形同虚设）。
            """
            while task["_pause"].is_set():
                with _tasks_lock:
                    task["status"] = "paused"
                await asyncio.sleep(0.1)
                if task["_cancel"].is_set():
                    return False
            with _tasks_lock:
                task["status"] = "downloading"
            return True

        async def _download_one(ch_data: dict):
            # ── 暂停/取消检查（章节开始前）──
            if not await _wait_if_paused():
                return

            ch = Chapter(id=ch_data["id"], url=ch_data["url"], novel_id=task["novel_id"],
                         title=ch_data["title"], order=ch_data["order"],
                         volume=ch_data.get("volume"))
            max_retries = 3
            t0 = time.time()
            downloaded = None
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    await asyncio.sleep(2 * attempt)
                # 书源级额度：同一书源同时最多 src_conc 个请求在飞（跨任务共享）。
                # 被取消时直接返回。
                if not await _acquire_source_slot(source_name, task, src_conc):
                    return
                # 拿到额度后才标记「下载中」：等额度期间保持 pending，前端不显示转圈
                # （标记早于取额度会让整批章节看起来同时在下载，与实际并发不符）。
                with _tasks_lock:
                    ch_data["status"] = "downloading"
                try:
                    downloaded = await resolve_chapter(ch, source_name, engines,
                                                       mode_overrides=_caps)
                except ChapterNotFoundError:
                    if attempt < max_retries:
                        continue
                    with _tasks_lock:
                        task["errors"].append(f"{ch.title}: 内容为空(已重试{max_retries}次)")
                        ch_data["status"] = "failed"
                        ch_data["error"] = f"内容为空(已重试{max_retries}次)"
                    break
                except Exception as e:
                    with _tasks_lock:
                        task["errors"].append(f"{ch.title}: {e}")
                        ch_data["status"] = "failed"
                        ch_data["error"] = str(e)
                    break
                else:
                    # ── 取消检查（下载完成后、落库前）──
                    if task["_cancel"].is_set():
                        return
                    if downloaded is not None:
                        store.save_chapter(novel, Chapters(chapters=[downloaded]))
                        with _tasks_lock:
                            task["current_title"] = downloaded.title
                            ch_data["status"] = "downloaded"
                    else:
                        with _tasks_lock:
                            task["errors"].append(f"章节不可获取: {ch.title}")
                            ch_data["status"] = "failed"
                            ch_data["error"] = "章节不可获取"
                    break
                finally:
                    # 每次 resolve_chapter（含重试）后释放书源额度
                    _release_source_slot(source_name)

            _update_eta(time.time() - t0)
            with _tasks_lock:
                task["progress"] += 1

        # 章节并发由书源额度决定（不再有任务内 Semaphore + max_workers）。
        # 分批提交：批内并发（受书源额度约束），批间串行。一次性挂起全部章节协程会让
        # 「等额度」的协程数 = 章节数，千章书下每个协程都按轮询抢同一书源额度 →
        # 海量无效唤醒 + 锁竞争（3000 章 ≈ 6 万次/s）。分批把同时挂起的协程压到
        # _BATCH_SIZE 量级；批间检查取消，保证取消仍能及时退出。
        async def _run_batches(chapters_list: list[dict]) -> None:
            for start in range(0, len(chapters_list), _BATCH_SIZE):
                if task["_cancel"].is_set():
                    return
                batch = chapters_list[start:start + _BATCH_SIZE]
                results = await asyncio.gather(
                    *(_download_one(ch) for ch in batch),
                    return_exceptions=True,
                )
                for r in results:
                    if isinstance(r, Exception):
                        _log.warning("章节下载协程异常", exc_info=r)

        await _run_batches(task["chapters"])

        # 收尾：被取消时不覆盖状态
        if task["_cancel"].is_set():
            return

        # 收尾检查点：暂停中等待 resume，然后重跑剩余 pending 章节
        while task["_pause"].is_set():
            if task["_cancel"].is_set():
                return
            with _tasks_lock:
                task["status"] = "paused"
            await asyncio.sleep(0.1)

        pending = [ch for ch in task["chapters"] if ch.get("status") == "pending"]
        if pending:
            await _run_batches(pending)

        if task["errors"]:
            task["status"] = "partial"
            task["error"] = f"部分章节下载失败 ({len(task['errors'])}/{task['total']})"
        else:
            task["status"] = "completed"
    except Exception as e:
        if task["_cancel"].is_set():
            return
        task["status"] = "failed"
        task["error"] = str(e)


def create_task(novel_id: str, chapters: list[dict], title: str,
                source_name: str = "", novel_url: str = "") -> dict:
    task_id = str(uuid.uuid4())[:8]
    # 给每章加初始状态
    ch_data = [
        {"id": c["id"], "url": c.get("url", ""), "title": c.get("title", ""),
         "order": c.get("order", 0), "status": "pending"}
        for c in chapters
    ]
    task = {
        "task_id": task_id, "novel_id": novel_id, "title": title,
        "total": len(chapters), "progress": 0, "status": "queued",
        "error": None, "errors": [], "current_title": "",
        "chapters": ch_data, "novel_url": novel_url,
        "created_at": time.time(),
        "_pause": asyncio.Event(),
        "_cancel": asyncio.Event(),
        "_source": source_name,
    }
    with _tasks_lock:
        _tasks[task_id] = task

    # create_task 是同步 def，但被 async 路由调用 → 事件循环正在运行，
    # 通过 get_running_loop() 拿当前 loop，把下载协程调度进去。
    loop = asyncio.get_running_loop()
    loop.create_task(_run_download(task, source_name))
    return {"task_id": task_id, "total": len(chapters)}


def list_tasks() -> list[dict]:
    """返回任务列表，含章节级状态（仅给最近章节供前端渲染面板）。"""
    with _tasks_lock:
        result = []
        to_remove = []
        for t in _tasks.values():
            if t["status"] == "cancelled":
                # cancelled 任务只保留 10 秒，让前端确认
                cancelled_at = t.get("_cancelled_at", 0)
                if time.time() - cancelled_at > 10:
                    to_remove.append(t["task_id"])
                    continue
            # 精简章节：传全部但每章只保留 title/order/status/error
            chapters = [
                {"title": c.get("title", ""), "order": c.get("order", 0),
                 "status": c.get("status", "pending"), "error": c.get("error")}
                for c in t.get("chapters", [])
            ]
            result.append({
                "task_id": t["task_id"], "novel_id": t["novel_id"], "title": t["title"],
                "total": t["total"], "progress": t["progress"], "status": t["status"],
                "error": t.get("error"), "errors": t.get("errors", []),
                "current_title": t.get("current_title", ""),
                "eta": t.get("eta"),
                "chapters": chapters,
                "source_name": t.get("_source", ""),
                "created_at": t.get("created_at"),
            })
        for tid in to_remove:
            _tasks.pop(tid, None)
        return result


def get_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


def pause_task(task_id: str) -> bool:
    """暂停任务：`downloading` 或排队的 `queued` 都可暂停（排队中暂停 = 置 _pause）。"""
    task = _tasks.get(task_id)
    if task and task.get("_pause") and task["status"] in ("downloading", "queued"):
        task["_pause"].set()
        return True
    return False


def resume_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if not task or not task.get("_pause"):
        return False
    if task["status"] == "paused":
        task["_pause"].clear()
        task["status"] = "downloading"
        return True
    if task["status"] == "queued" and task["_pause"].is_set():
        # 排队中被暂停：清标志，status 保持 queued（等额度；拿到后转 downloading）
        task["_pause"].clear()
        return True
    if task["status"] == "failed":
        task["_pause"].clear()
        task["_cancel"].clear()
        task["status"] = "downloading"
        task["error"] = None
        task["errors"] = []
        task["progress"] = 0
        for c in task["chapters"]:
            c["status"] = "pending"
        loop = asyncio.get_running_loop()
        loop.create_task(_run_download(task, task.get("_source", "")))
        return True
    return False


def delete_task(task_id: str) -> bool:
    """真正取消下载：设 _cancel 标志 + status=cancelled，下载协程检测到后停止。

    对排队中（`queued`）任务同样有效：协程在拿到额度后立即检查 _cancel 并退出。
    """
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return False
        task["_cancel"].set()
        task["status"] = "cancelled"
        task["_cancelled_at"] = time.time()
        # 唤醒可能被暂停的 worker
        if task.get("_pause") and task["_pause"].is_set():
            task["_pause"].clear()
        return True
