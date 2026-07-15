import json
import re
import time
from typing import Sequence, Any

import requests
from bs4 import BeautifulSoup, Tag

from .base import BaseFetcher
from ..core.exceptions import AntiCrawlError, ChapterNotFoundError, FeatureNotSupportedError, NovelNotFoundError, ParseError
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, SearchResult, Illustration, Chapters
from ..utils.logger import get_logger

_log = get_logger("novelbase.fetchers.fanqie")

# 字符转码表
content_transcoding = {"58670": "0", "58413": "1", "58678": "2", "58371": "3", "58353": "4", "58480": "5", "58359": "6",
                       "58449": "7", "58540": "8", "58692": "9", "58712": "a", "58542": "b", "58575": "c", "58626": "d",
                       "58691": "e", "58561": "f", "58362": "g", "58619": "h", "58430": "i", "58531": "j", "58588": "k",
                       "58440": "l", "58681": "m", "58631": "n", "58376": "o", "58429": "p", "58555": "q", "58498": "r",
                       "58518": "s", "58453": "t", "58397": "u", "58356": "v", "58435": "w", "58514": "x", "58482": "y",
                       "58529": "z", "58515": "A", "58688": "B", "58709": "C", "58344": "D", "58656": "E", "58381": "F",
                       "58576": "G", "58516": "H", "58463": "I", "58649": "J", "58571": "K", "58558": "L", "58433": "M",
                       "58517": "N", "58387": "O", "58687": "P", "58537": "Q", "58541": "R", "58458": "S", "58390": "T",
                       "58466": "U", "58386": "V", "58697": "W", "58519": "X", "58511": "Y", "58634": "Z",
                       "58611": "的", "58590": "一", "58398": "是", "58422": "了", "58657": "我", "58666": "不",
                       "58562": "人", "58345": "在", "58510": "他", "58496": "有", "58654": "这", "58441": "个",
                       "58493": "上", "58714": "们", "58618": "来", "58528": "到", "58620": "时", "58403": "大",
                       "58461": "地", "58481": "为", "58700": "子", "58708": "中", "58503": "你", "58442": "说",
                       "58639": "生", "58506": "国", "58663": "年", "58436": "着", "58563": "就", "58391": "那",
                       "58357": "和", "58354": "要", "58695": "她", "58372": "出", "58696": "也", "58551": "得",
                       "58445": "里", "58408": "后", "58599": "自", "58424": "以", "58394": "会", "58348": "家",
                       "58426": "可", "58673": "下", "58417": "而", "58556": "过", "58603": "天", "58565": "去",
                       "58604": "能", "58522": "对", "58632": "小", "58622": "多", "58350": "然", "58605": "于",
                       "58617": "心", "58401": "学", "58637": "么", "58684": "之", "58382": "都", "58464": "好",
                       "58487": "看", "58693": "起", "58608": "发", "58392": "当", "58474": "没", "58601": "成",
                       "58355": "只", "58573": "如", "58499": "事", "58469": "把", "58361": "还", "58698": "用",
                       "58489": "第", "58711": "样", "58457": "道", "58635": "想", "58492": "作", "58647": "种",
                       "58623": "开", "58521": "美", "58609": "总", "58530": "从", "58665": "无", "58652": "情",
                       "58676": "己", "58456": "面", "58581": "最", "58509": "女", "58488": "但", "58363": "现",
                       "58685": "前", "58396": "些", "58523": "所", "58471": "同", "58485": "日", "58613": "手",
                       "58533": "又", "58589": "行", "58527": "意", "58593": "动", "58699": "方", "58707": "期",
                       "58414": "它", "58596": "头", "58570": "经", "58660": "长", "58364": "儿", "58526": "回",
                       "58501": "位", "58638": "分", "58404": "爱", "58677": "老", "58535": "因", "58629": "很",
                       "58577": "给", "58606": "名", "58497": "法", "58662": "间", "58479": "斯", "58532": "知",
                       "58380": "世", "58385": "什", "58405": "两", "58644": "次", "58578": "使", "58505": "身",
                       "58564": "者", "58412": "被", "58686": "高", "58624": "已", "58667": "亲", "58607": "其",
                       "58616": "进", "58368": "此", "58427": "话", "58423": "常", "58633": "与", "58525": "活",
                       "58543": "正", "58418": "感", "58597": "见", "58683": "明", "58507": "问", "58621": "力",
                       "58703": "理", "58438": "尔", "58536": "点", "58384": "文", "58484": "几", "58539": "定",
                       "58554": "本", "58421": "公", "58347": "特", "58569": "做", "58710": "外", "58574": "孩",
                       "58375": "相", "58645": "西", "58592": "果", "58572": "走", "58388": "将", "58370": "月",
                       "58399": "十", "58651": "实", "58546": "向", "58504": "声", "58419": "车", "58407": "全",
                       "58672": "信", "58675": "重", "58538": "三", "58465": "机", "58374": "工", "58579": "物",
                       "58402": "气", "58702": "每", "58553": "并", "58360": "别", "58389": "真", "58560": "打",
                       "58690": "太", "58473": "新", "58512": "比", "58653": "才", "58704": "便", "58545": "夫",
                       "58641": "再", "58475": "书", "58583": "部", "58472": "水", "58478": "像", "58664": "眼",
                       "58586": "等", "58568": "体", "58674": "却", "58490": "加", "58476": "电", "58346": "主",
                       "58630": "界", "58595": "门", "58502": "利", "58713": "海", "58587": "受", "58548": "听",
                       "58351": "表", "58547": "德", "58443": "少", "58460": "克", "58636": "代", "58585": "员",
                       "58625": "许", "58694": "稜", "58428": "先", "58640": "口", "58628": "由", "58612": "死",
                       "58446": "安", "58468": "写", "58410": "性", "58508": "马", "58594": "光", "58483": "白",
                       "58544": "或", "58495": "住", "58450": "难", "58643": "望", "58486": "教", "58406": "命",
                       "58447": "花", "58669": "结", "58415": "乐", "58444": "色", "58549": "更", "58494": "拉",
                       "58409": "东", "58658": "神", "58557": "记", "58602": "处", "58559": "让", "58610": "母",
                       "58513": "父", "58500": "应", "58378": "直", "58680": "字", "58352": "场", "58383": "平",
                       "58454": "报", "58671": "友", "58668": "关", "58452": "放", "58627": "至", "58400": "张",
                       "58455": "认", "58416": "接", "58552": "告", "58614": "入", "58582": "笑", "58534": "内",
                       "58701": "英", "58349": "军", "58491": "侯", "58467": "民", "58365": "岁", "58598": "往",
                       "58425": "何", "58462": "度", "58420": "山", "58661": "觉", "58615": "路", "58648": "带",
                       "58470": "万", "58377": "男", "58520": "边", "58646": "风", "58600": "解", "58431": "叫",
                       "58715": "任", "58524": "金", "58439": "快", "58566": "原", "58477": "吃", "58642": "妈",
                       "58437": "变", "58411": "通", "58451": "师", "58395": "立", "58369": "象", "58706": "数",
                       "58705": "四", "58379": "失", "58567": "满", "58373": "战", "58448": "远", "58659": "格",
                       "58434": "士", "58679": "音", "58432": "轻", "58689": "目", "58591": "条", "58682": "呢"}


def translate(en_text: str | None) -> str:
    if not en_text: return ''
    de_text = ''
    transcoding = content_transcoding
    for index in en_text:
        t1 = ''
        try:
            t1 = transcoding[str(ord(index))]
        except KeyError:
            t1 = index
        finally:
            de_text += t1
    return de_text

def extract_json(html_content: str) -> dict[str, Any]:

    start = html_content.find("window.__INITIAL_STATE__=")
    if start == -1:
        return {}

    start += len("window.__INITIAL_STATE__=")
    start_html = html_content[start:]
    end = start_html.find(")()")
    script = start_html[:end].strip()[:-1].strip()[:-1]
    script = script.replace('"libra":undefined', '"libra":"undefined"')

    json_data = json.loads(script)
    return json_data

def standardize_id(ref: str | Novel | Chapter) -> str:

    if isinstance(ref, Novel):
        ref = ref.url
    if isinstance(ref, Chapter):
        ref = ref.url
    if isinstance(ref, str):
        if re.match(r"^\d{19}$",ref):
            return ref
        if search := re.search(r"book_id=(\d{19})",ref):
            return search.group(1)
        if search := re.search(r"\d{19}", ref):
            return search.group(0)
    raise ValueError(f"ref {ref} Non conformance")


def resolve_changdunovel(url: str) -> str:
    """解析 changdunovel.com 短链，提取 book_id 返回标准 fanqienovel URL。"""
    if "changdunovel.com" not in url:
        return url
    try:
        r = requests.get(url, allow_redirects=True, timeout=10)
        book_id = standardize_id(r.url)
        return f"https://fanqienovel.com/page/{book_id}"
    except (requests.RequestException, ValueError):
        return url


# 通过html获取小说相关信息
class FanqieHTMLParser:

    @staticmethod
    def parse_search_result(data: dict[str, Any]) -> tuple[SearchResult, ...]:
        results: list[SearchResult] = []
        if data.get("data") and data["data"].get("ret_data"):
            for book_info in data["data"]["ret_data"]:
                book_id = book_info.get("book_id")
                book_url = f"https://fanqienovel.com/page/{book_id}"
                book_name = book_info.get("title")
                author = book_info.get("author")
                description = book_info.get("abstract")

                results.append(SearchResult(
                    title=book_name,
                    author=author,
                    url=book_url,
                    description=description,
                ))

        return tuple(results)

    @staticmethod
    def parse_novel_info(html: str) -> Novel:

        if BeautifulSoup(html, 'lxml').find("div", class_="no-content"):
            raise NovelNotFoundError()

        json_data = extract_json(html)
        if not json_data:
            raise NovelNotFoundError()

        page_data = json_data.get('page')
        book_url = f"https://fanqienovel.com/page/{page_data['bookId']}"
        name = page_data.get("bookName")
        author = page_data.get("author")
        label_item_str = page_data.get("categoryV2")
        label_item_list = json.loads(label_item_str)
        status = page_data.get("creationStatus")
        label_list = []
        if status == 1:
            label_list.append("连载中")
        else:
            label_list.append("已完结")

        for label_item in label_item_list:
            label_list.append(label_item.get("Name"))
        count_word = page_data.get("wordNumber")
        abstract = page_data.get("abstract")

        book_cover_url = page_data.get("thumbUri")
        try:
            book_cover_data = requests.get(book_cover_url, timeout=10).content
        except requests.RequestException:
            book_cover_data = b""
        cover_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)
        chapter_list_with_volume = json_data.get("page", {}).get("chapterListWithVolume", {})
        serial = 0
        for chapters_list in chapter_list_with_volume:serial += len(chapters_list)

        novel = Novel(url=book_url,
                      id = standardize_id(book_url),
                      title=name,
                      author=author,
                      serial=serial,
                      tags=tuple(label_list),
                      description=abstract,
                      count=count_word,
                      cover=cover_image
                      )
        return novel

    @staticmethod
    def parse_chapter_list(html: str) -> Chapters:

        if BeautifulSoup(html, 'lxml').find("div", class_="no-content"):
            raise ChapterNotFoundError("Chapter list page shows no-content div")
        json_data = extract_json(html)
        if not json_data:
            raise ChapterNotFoundError("Chapter list JSON extraction returned empty")

        chapter_list_with_volume = json_data.get("page").get("chapterListWithVolume")
        book_url = "https://fanqienovel.com/page/" + json_data.get("page", {}).get("bookId")
        chapter_list = []

        for chapters_list in chapter_list_with_volume:
            for chapter_item in chapters_list:
                title = chapter_item["title"]
                chapter_url = 'https://fanqienovel.com/reader/' + chapter_item.get("itemId")
                first_pass_time = int(chapter_item.get("firstPassTime", 0))
                order = int(chapter_item.get("realChapterOrder"))
                volume_name = chapter_item.get("volume_name")
                chapter = Chapter(title=title,
                                  url=chapter_url,
                                  novel_id=standardize_id(book_url),
                                  id = standardize_id(chapter_url),
                                  volume=volume_name,
                                  order=order,
                                  time=first_pass_time)
                chapter_list.append(chapter)

        return Chapters(chapter_list)

    @staticmethod
    def parse_chapter_content(html: str, chapter: Chapter) -> Chapter | None:
        """解析并填充content, count, images, """

        if BeautifulSoup(html, 'lxml').find("div", class_="no-content"):
            raise ChapterNotFoundError("Chapter page shows no-content div")
        if "window.__INITIAL_STATE__=" not in html:
            raise ParseError("Chapter page missing __INITIAL_STATE__")

        json_data = extract_json(html)
        if not json_data:
            raise ChapterNotFoundError("Chapter JSON extraction returned empty")
        count = json_data.get("reader", {}).get("chapterData", {}).get("chapterWordNumber")
        parent_soup = BeautifulSoup(html, 'lxml')
        if parent_soup.find('div', class_='muye-to-fanqie'):
            return None

        html_content = str(parent_soup.find('div', class_='muye-reader-content noselect'))
        soup = BeautifulSoup(translate(html_content), 'lxml')

        content_div = soup.find('div', class_='muye-reader-content noselect')
        if not content_div:
            content_div = soup.find('div', class_='muye-reader-content')

        separator = "\n\n"
        img_counter = 0
        img_tasks: list[dict] = []  # 收集图片下载任务，后面批量并发
        text_paragraphs: list[str] = []

        # 按直接子元素顺序遍历，同时提取文本和图片位置
        if content_div:
            inner = content_div.find('div')
            target = inner if inner else content_div

            for element in target.children:
                if not isinstance(element, Tag):
                    text = element.strip() if isinstance(element, str) else ''
                    if text:
                        text_paragraphs.append(text)
                    continue

                if element.name == 'p':
                    cls = element.get('class') or []

                    if 'picture' in cls:
                        # 图片段落
                        img_tag = element.find('img')
                        if img_tag:
                            img_counter += 1
                            group_id = img_counter

                            # 获取图片描述
                            picture_desc = ""
                            pic_desc_p = element.find_next_sibling('p', class_='pictureDesc')
                            if not pic_desc_p:
                                parent = element.parent
                                while parent and isinstance(parent, Tag):
                                    if parent.name == 'div' and parent.get('data-fanqie-type') == 'image':
                                        pic_desc_tag = parent.find('p', class_='pictureDesc')
                                        if pic_desc_tag and isinstance(pic_desc_tag, Tag):
                                            if pic_desc_tag.get('group-id') == str(group_id):
                                                picture_desc = pic_desc_tag.get_text(strip=True)
                                        break
                                    if parent.name == 'p' and 'pictureDesc' in (parent.get('class') or []):
                                        picture_desc = parent.get_text(strip=True)
                                        break
                                    parent = parent.parent
                            else:
                                if pic_desc_p.get('group-id') == str(group_id):
                                    picture_desc = pic_desc_p.get_text(strip=True)

                            img_url = img_tag.get('src', '')
                            if isinstance(img_url, list):
                                img_url = img_url[0] if img_url else None
                            if isinstance(img_url, str) and img_url.strip():
                                prefix = separator.join(text_paragraphs)
                                insert_pos = len(prefix) if text_paragraphs else 0
                                img_tasks.append(dict(
                                    url=img_url, alt=picture_desc, insert=insert_pos
                                ))
                        continue

                    text = element.get_text(strip=True)
                    if text:
                        text_paragraphs.append(text)

                elif element.name == 'div' and element.get('data-fanqie-type') == 'image':
                    img_tag = element.find('img')
                    if img_tag:
                        img_counter += 1
                        group_id = img_counter

                        picture_desc = ""
                        pic_desc_tag = element.find('p', class_='pictureDesc')
                        if pic_desc_tag and isinstance(pic_desc_tag, Tag):
                            if pic_desc_tag.get('group-id') == str(group_id):
                                picture_desc = pic_desc_tag.get_text(strip=True)

                        img_url = img_tag.get('src', '')
                        if isinstance(img_url, list):
                            img_url = img_url[0] if img_url else None
                        if isinstance(img_url, str) and img_url.strip():
                            prefix = separator.join(text_paragraphs)
                            insert_pos = len(prefix) if text_paragraphs else 0
                            img_tasks.append(dict(
                                url=img_url, alt=picture_desc, insert=insert_pos
                            ))

        # 并发下载所有图片
        img_items: list[Illustration] = []
        if img_tasks:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=5) as pool:
                def _download_one(task: dict) -> tuple[int, bytes]:
                    try:
                        return (task.get("_idx", 0), requests.get(task["url"], timeout=10).content)
                    except requests.RequestException:
                        return (task.get("_idx", 0), b"")
                # 标记原始顺序
                for i, t in enumerate(img_tasks):
                    t["_idx"] = i
                results: dict[int, bytes] = {}
                for fut in as_completed([pool.submit(_download_one, t) for t in img_tasks]):
                    idx, data = fut.result()
                    results[idx] = data
            # 按原始顺序构造 Illustration
            for i, t in enumerate(img_tasks):
                img_data = results.get(i, b"")
                img_items.append(Illustration(
                    alt=t["alt"], raw_data=img_data,
                    insert=t["insert"], url=t["url"]
                ))

        novel_content = separator.join(text_paragraphs)
        if '已经是最新一章' in novel_content:
            novel_content = novel_content.replace('已经是最新一章', '')

        chapter.count = count
        chapter.content = novel_content
        chapter.images = tuple(img_items)
        return chapter

class FanqieBrowserFetcher(BaseFetcher):

    def login(self, engine, **kwargs) -> AuthCredential:
        _log.info("login start")
        page = engine.new_page()

        try:
            page.get("https://fanqienovel.com/")

            print("请在打开的浏览器窗口中完成登录（扫码/手机号）...")
            deadline = time.time() + 120
            while time.time() < deadline:
                if "author" in page.url:
                    break
                time.sleep(0.5)

            time.sleep(2)
            _log.info("login completed")

            raw_cookies = page.cookies()
            cookies = {c["name"]: c["value"] for c in raw_cookies}

            headers = {}

            return AuthCredential(
                cookies=cookies,
                headers=headers,
                extra={}
            )
        finally:
            page.close()

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        _log.debug("parse_search_info: ref=%s page=%s", query, page)
        offset = (page - 1) * 10
        search_url = f"https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/?aid=1967&offset={offset}&q={query}"
        try:
            query = requests.get(search_url).json()
        except Exception as exc:
            _log.warning("search API failed: %s", exc)
            return ()
        return FanqieHTMLParser.parse_search_result(data=query)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        url = f"https://fanqienovel.com/page/{standardize_id(url)}"
        html = engine.fetch_text(url=url, **kwargs)
        novel = FanqieHTMLParser.parse_novel_info(html=html)
        return novel

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        url = f"https://fanqienovel.com/page/{standardize_id(url)}"
        html = engine.fetch_text(url=url, **kwargs)
        chapter_list = FanqieHTMLParser.parse_chapter_list(html=html)
        return Chapters(chapter_list)

    def fetch_chapter_content(
            self,
            chapter: Chapter,
            engine,
            **kwargs) -> Chapter | None:

        url = f"https://fanqienovel.com/reader/{standardize_id(chapter)}"
        html = engine.fetch_text(url=url, **kwargs)

        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError("Chapter page shows no-content div")

        result = FanqieHTMLParser.parse_chapter_content(html, chapter)
        return result

class FanqieOIAPIFetcher(BaseFetcher):

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        results: list[SearchResult] = []
        post_data = {
            "page": page,
            "keyword": query,
            "key": engine.options.key,
            "method": "search",
            "type": "json"
        }
        content = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

        if content.get("data"):
            book_info_list = content.get("data")
            for book_info in book_info_list:
                book_id = book_info.get("id")
                book_url = f"https://fanqienovel.com/page/{book_id}"
                book_name = book_info.get("title")
                author = book_info.get("author")
                description = book_info.get("docs")

                results.append(SearchResult(
                    title=book_name,
                    author=author,
                    url=book_url,
                    description=description,
                ))

        return tuple(results)

    def fetch_novel_info(self, url, engine, **kwargs) -> Novel:

        novel_id = standardize_id(url)
        post_data = {
            "chapter": 0,
            "id": novel_id,
            "key": engine.options.key,
            "type": "json"
        }
        json_data = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

        data = json_data.get('data')
        if not data:
            raise NovelNotFoundError()
        else:
            serial: int = int(data.get("serial", 0))
            url = f"https://fanqienovel.com/page/{data.get('id')}"
            book_cover_url = data.get('thumb')
            try:
                book_cover_data = requests.get(book_cover_url, timeout=10).content
            except requests.RequestException:
                book_cover_data = b""
            name = data.get('title')
            novel_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)
            author = data.get('author')
            word_number: int = int(data.get('word_number', 0))

            novel = Novel(url=url,
                          id=novel_id,
                          title=name,
                          serial=serial,
                          author=author,
                          count=word_number,
                          description=data.get('docs'),
                          cover=novel_image
                          )
            return novel

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:

        novel_id = standardize_id(url)
        post_data = {
            "id": novel_id,
            "key": engine.options.key,
            "method": "chapters",
            "type": "json"
        }
        json_data = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

        chapter_items_volume = json_data.get('data')
        if not chapter_items_volume:
            raise ChapterNotFoundError("OIAPI returned empty chapter list")
        results = []

        for chapter_items in chapter_items_volume:
            for chapter_item in chapter_items:
                chapter_id: int = chapter_item.get("chapter_id")
                chapter_url = "https://fanqienovel.com/reader/" + str(chapter_id)
                title: str = chapter_item["title"]
                order: int = chapter_item["index"]
                timestamp: float = chapter_item["time"]
                volume_name = chapter_item["volume_name"]
                chapter = Chapter(
                    title=title,
                    url=chapter_url,
                    id = str(chapter_id),
                    order=order,
                    novel_id=standardize_id(url),
                    volume=volume_name,
                    time=timestamp
                )
                results.append(chapter)

        return Chapters(results)

    def fetch_chapter_content(self, chapter: Chapter, engine, **kwargs) -> Chapter | None:
        """解析并填充content, count, (True)"""
        novel_id = standardize_id(chapter.novel_id)
        post_data = {
            "id": novel_id,
            "chapter": str(chapter.order),
            "key": engine.options.key,
            "method": "chapter",
            "type": "json"
        }
        response = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

        data_list: dict = response.get('data', {})
        if not data_list:
            message = response.get('message', "")
            if message == "请检测章节选择是否正确":
                raise ChapterNotFoundError(message=f"Invalid chapter order: {chapter.order}")
            elif message == "实例化失败: Trying to access array offset on value of type bool line 197in api.php":
                raise AntiCrawlError("OIAPI request frequency too high, PHP backend rejected")
            else:
                raise ChapterNotFoundError(message=f"OIAPI unexpected response: {message}")

        for data in data_list.values() if isinstance(data_list, dict) else []:
            chapter.content = data.get('content', '').replace(f"{data.get('chapter_title', '')}\n\n", "")
            chapter.count = data.get('word_number', 0)
            break

        return chapter

class FanqieRainFetcher(BaseFetcher):

    def login(self, engine, **kwargs):
        raise FeatureNotSupportedError("Not Supported login by the Rain API")

    @staticmethod
    def _api_url(engine, **params) -> str:
        key = engine.options.key
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        base = f"https://v3.rain.ink/fanqie/?apikey={key}"
        return f"{base}&{qs}" if qs else base

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        results: list[SearchResult] = []
        offset = (page - 1) * 10
        url = FanqieRainFetcher._api_url(engine, type=1, keywords=query, page=offset)
        content = engine.fetch_json(url, **kwargs)

        if content.get("code") != 0 and str(content.get("code")) != "0":
            return ()

        books = None
        if "search_tabs" in content:
            for tab in content["search_tabs"]:
                if tab.get("data") is not None:
                    books = tab["data"]
                    break
        if books is None:
            books = content.get("data")

        if not books or not isinstance(books, list):
            return ()

        for item in books:
            if "book_data" in item and isinstance(item["book_data"], list) and len(item["book_data"]) > 0:
                book = item["book_data"][0]
            else:
                book = item

            book_id = book.get("book_id")
            book_url = f"https://fanqienovel.com/page/{book_id}"
            book_name = book.get("book_name")
            author = book.get("author")
            description = book.get("abstract")

            results.append(SearchResult(
                title=book_name,
                author=author,
                url=book_url,
                description=description,
            ))
        return tuple(results)

    def fetch_novel_info(self, url, engine, **kwargs) -> Novel:

        novel_id = standardize_id(url)
        url = FanqieRainFetcher._api_url(engine, type=2, bookid=novel_id)
        json_data = engine.fetch_json(url, **kwargs)

        if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
            raise NovelNotFoundError()

        data = json_data.get("data")
        if not data:
            raise NovelNotFoundError()

        book_url = f"https://fanqienovel.com/page/{data.get('book_id')}"
        name = data.get("book_name")

        author = ""
        author_info = data.get("author_info")
        if author_info and isinstance(author_info, dict):
            author = author_info.get("user_name", "")
        if not author:
            try:
                original_authors = json.loads(data.get("original_authors", "[]"))
                if original_authors:
                    author = original_authors[0].get("AuthorName", "")
            except (json.JSONDecodeError, IndexError):
                pass

        serial = int(data.get("serial_count", 0))
        word_number = int(data.get("word_number", 0))

        cover_url = data.get("thumb_url", "")
        try:
            book_cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
        except requests.RequestException:
            book_cover_data = b""
        novel_image = Illustration(raw_data=book_cover_data, alt=name, url=cover_url)

        tags: list[str] = []
        status = data.get("status", "0")
        tags.append("连载中" if status == "0" else "已完结")
        try:
            category_v2 = json.loads(data.get("category_v2", "[]"))
            for cat in category_v2:
                cat_name = cat.get("Name")
                if cat_name:
                    tags.append(cat_name)
        except json.JSONDecodeError:
            pass

        novel = Novel(url=book_url,
                      id=novel_id,
                      title=name,
                      serial=serial,
                      author=author,
                      count=word_number,
                      description=data.get("abstract", ""),
                      cover=novel_image,
                      tags=tuple(tags),
                      )
        return novel

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:

        novel_id = standardize_id(url)
        url = FanqieRainFetcher._api_url(engine, type=3, bookid=novel_id)
        json_data = engine.fetch_json(url, **kwargs)

        if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
            raise ChapterNotFoundError(f"Rain API returned error code: {json_data.get('code')}")

        item_data_list = json_data.get("data", {}).get("item_data_list")
        if not item_data_list:
            raise ChapterNotFoundError("Rain API returned empty chapter list")

        results: list[Chapter] = []
        for idx, chapter_item in enumerate(item_data_list):
            item_id = chapter_item.get("item_id")
            chapter_url = f"https://fanqienovel.com/reader/{item_id}"
            title: str = chapter_item.get("title", "")
            volume_name = chapter_item.get("volume_name", "")
            first_pass_time: float = chapter_item.get("first_pass_time", 0)
            chapter = Chapter(
                title=title,
                url=chapter_url,
                id=str(item_id),
                order=idx,
                novel_id=novel_id,
                volume=volume_name,
                time=first_pass_time,
            )
            results.append(chapter)
        return Chapters(results)

    def fetch_chapter_content(self, chapter: Chapter, engine, **kwargs) -> Chapter | None:
        """解析并填充content, count, (True)"""
        item_id = standardize_id(chapter)
        url = FanqieRainFetcher._api_url(engine, type=4, itemid=item_id)
        response = engine.fetch_json(url, **kwargs)

        if response.get("code") != 0 and str(response.get("code")) != "0":
            err_msg = response.get("data", {}).get("content", "Unknown error")
            raise ChapterNotFoundError(message=f"Chapter content error: {err_msg}")

        data = response.get("data", {})
        title = data.get("title", "")
        raw_content = data.get("content", "")
        content = raw_content.strip()
        content = content.replace("</p>", "\n\n")
        if content.startswith(title):
            content = content[len(title):].strip()

        chapter.content = content
        chapter.count = len(content)

        return chapter

class FanqieRequestsFetcher(BaseFetcher):

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        _log.debug("parse_search_info: ref=%s page=%s", query, page)
        offset = (page - 1) * 10
        search_url = f"https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/?aid=1967&offset={offset}&q={query}"
        try:
            query = requests.get(search_url).json()
        except Exception as exc:
            _log.warning("search API failed: %s", exc)
            return ()
        return FanqieHTMLParser.parse_search_result(data=query)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        url = f"https://fanqienovel.com/page/{standardize_id(url)}"
        html = engine.fetch_text(url=url, **kwargs)
        novel = FanqieHTMLParser.parse_novel_info(html=html)

        return novel

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        url = f"https://fanqienovel.com/page/{standardize_id(url)}"
        html = engine.fetch_text(url=url, **kwargs)
        chapter_list = FanqieHTMLParser.parse_chapter_list(html=html)
        return Chapters(chapter_list)

    def fetch_chapter_content(
            self,
            chapter,
            engine,
            **kwargs) -> Chapter | None:
        url = f"https://fanqienovel.com/reader/{standardize_id(chapter)}"
        html = engine.fetch_text(url=url, **kwargs)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError("Chapter page shows no-content div")
        result = FanqieHTMLParser.parse_chapter_content(html, chapter)
        return result

def use_fetcher(engine) -> type[FanqieRequestsFetcher] | type[FanqieBrowserFetcher] | type[FanqieOIAPIFetcher] | type[FanqieRainFetcher]:
    if engine.name == "browser":
        return FanqieBrowserFetcher
    elif engine.name == "requests":
        return FanqieRequestsFetcher
    elif engine.name == "API":
        api_name = engine.options.name
        if api_name is None or api_name == "oiapi":
            return FanqieOIAPIFetcher
        if api_name == "rain":
            return FanqieRainFetcher
        raise ValueError(
            f"Unsupported API backend: {api_name!r}. "
            f"Only 'oiapi' and 'rain' are supported."
        )
    else:
        raise ValueError(f"Unknown engine: {engine.name}")

class FanqieFetcher(BaseFetcher):
    host = ("fanqienovel.com","changdunovel.com")
    id_pattern = re.compile(r"^(?:book_id=?)?(\d{19})$")

    def login(self, engine, **kwargs) -> AuthCredential:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.login(engine=engine, **kwargs)

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_search_result(query=query, engine=engine, **kwargs)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        url = resolve_changdunovel(url)
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_novel_info(url=url, engine=engine, **kwargs)

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        url = resolve_changdunovel(url)
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_chapter_list(url=url, engine=engine, **kwargs)

    def fetch_chapter_content(self,
                              chapter: Chapter,
                              engine,
                              **kwargs) -> Chapter | None:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_chapter_content(chapter=chapter, engine=engine, **kwargs)