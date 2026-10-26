from bs4 import BeautifulSoup

from novelbase.core.exceptions import AntiCrawlError, NovelNotFoundError, ParseError
from novelbase.models.novel import Illustration, Novel


def content_is_exist(html: str) -> bool:

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one("title")
    if title_tag and title_tag.get_text() == "WAF拦截页面":
        raise AntiCrawlError()

    h1_tag = soup.select_one("h1")
    if h1_tag and h1_tag.get_text() == "抱歉，页面无法访问...":
        return False
    return True

def parse_novel_info(html: str, url) -> Novel:
    soup = BeautifulSoup(html, 'lxml')

    if not content_is_exist(html):
        raise NovelNotFoundError()

    try:
        serial = len(soup.select("div.catalog-all li"))

        name = soup.select_one('h1#bookName').get_text()

        intro_tag = soup.select_one("p.book-desc")
        intro = intro_tag.get_text() if intro_tag else None
        if soup.select_one('div.author-information'):
            author = soup.select_one('a.writer-name').get_text()
            attribute_str = soup.select_one('p.book-attribute').text
            attribute = attribute_str.split('·')
            all_label = attribute
        else:
            all_label = []
            author = soup.select_one('span.author').get_text()

        count_word_str = soup.select_one('p.count em').get_text()
        if count_word_str.endswith("万"):
            count_word = int(float(count_word_str[:-1]) * 10000)
        else:
            count_word = int(count_word_str)

        intro_detail = soup.select_one('p#book-intro-detail').get_text()
        abstract = f'{intro}\n{intro_detail}' if intro else intro_detail

        book_cover_url = 'https:' + soup.select_one('a#bookImg img').get('src')
    except AttributeError as exc:
        raise ParseError("Qidian novel info page missing expected element", detail=str(exc)) from exc
    # 封面字节由能力函数经 engine.async_fetch_images 下载
    novel_image = Illustration(raw_data=b"", alt=name, url=book_cover_url)

    return Novel(
        url=url,
        title=name,
        serial=serial,
        author=author,
        count=count_word,
        description=abstract,
        tags=all_label,
        cover=novel_image,
    )

async def novel_info(url: str, engine, **kwargs):
    html = await engine.async_fetch_text(url=url, **kwargs)
    novel = parse_novel_info(html, url=url)
    if novel.cover and novel.cover.url:
        data = await engine.async_fetch_images([novel.cover.url])
        novel.cover = Illustration(
            raw_data=data[0], alt=novel.cover.alt, url=novel.cover.url
        )
    return novel
