from pathlib import Path

sample_dir = Path(__file__).parent / "sample"
from nldlder.core.storage import Storage
from nldlder.core.options import Options
from nldlder.parsers.fanqie import FanqieHTMLParser
storage = Storage(Options().storage)
novel_id = "7499553647647263806"
novel = storage.load_meta(novel_id)
if novel is None:
    exit(1)
local_chapters = storage.load_chapters(novel_id)

from nldlder.exporters.epub import EPUBExporter, EPUBExportOptions
options = EPUBExportOptions(output_path=Path(__file__).parent / "app_data" / "epub")
exporter = EPUBExporter(novel=novel, options=options)
parser = FanqieHTMLParser()
for file in sample_dir.glob("*.html"):
    data = file.read_text(encoding="utf-8")
    stem = int(file.stem)
    chapter = parser.parse_chapter_content(chapter_ref=data, engine=None, chapter = local_chapters.get_chapter_by_order(stem))
    novel.update_chapter(chapter)
exporter.export(novel.chapters)
