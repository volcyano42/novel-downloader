import time
from dataclasses import dataclass
from pathlib import Path

from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel


@dataclass
class TXTExportOptions(ExportOptions):
    format: str = "txt"
    encoding: str = "utf-8"


def _build_file_path(novel: Novel, options: TXTExportOptions) -> Path:
    from datetime import datetime
    from ..utils.template_utils import SafeDict

    file_name_template = getattr(options, "file_name_template", "{title}")
    variables = SafeDict({
        "title": novel.title if novel else "",
        "author": novel.author if novel else "",
        "novel_id": novel.id if novel else "",
        "total_chapters": novel.serial if novel else 0,
        "date": datetime.now().strftime("%Y%m%d"),
    })
    raw_path = str(getattr(options, "output_path", "."))
    output_dir = Path(raw_path.format_map(variables))
    filename = file_name_template.format(**variables)
    return output_dir / f"{filename}.txt"


def _generate_info_text(novel: Novel) -> str:
    if not novel:
        return ""
    return (
        f"小说名：{novel.title}\n"
        f"作者：{novel.author}\n"
        f"简介：{novel.description}\n"
        f"标签：{' '.join(novel.tags) if novel.tags else ''}\n"
        f"章节数：{len(novel.chapters)}/{novel.serial}\n"
        f"字数：{novel.count}\n"
        f"链接：{novel.url}\n\n"
    )


def _format_chapter(chapter: Chapter) -> str:
    if isinstance(chapter.content, str):
        content = '\t' + chapter.content.replace("\n", "\n\t")
    else:
        content = str(chapter.content) if chapter.content else ""
    return (
        f"{chapter.title}\n\n"
        f"更新字数：{chapter.count}\n"
        f"更新时间：{time.strftime('%Y-%m-%d %H:%M', time.localtime(chapter.time)) if chapter.time else '未知'}\n\n"
        f"{content}\n\n"
    )


def export(
    chapters,
    novel: Novel,
    options: TXTExportOptions | None = None,
    **kwargs,
) -> Path:
    """一次性导出 TXT，返回输出文件路径。"""
    if options is None:
        options = TXTExportOptions()
    encoding = getattr(options, "encoding", "utf-8")
    file_path = _build_file_path(novel, options)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(chapters, Chapter):
        chapters_list = [chapters]
    else:
        chapters_list = list(chapters)
    chapters_list = [c for c in chapters_list if c.content is not None]
    chapters_list.sort(key=lambda c: c.order)

    with open(file_path, "w", encoding=encoding) as f:
        f.write(_generate_info_text(novel))
        for ch in chapters_list:
            f.write(_format_chapter(ch))

    return file_path


