import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from novelbase.core.exceptions import ChapterNotFoundError, NovelNotFoundError, ParseError
from novelbase.models.novel import Novel, Chapter, SearchResult, Illustration, Chapters

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
        if re.match(r"^\d{19}$", ref):
            return ref
        if search := re.search(r"book_id=(\d{19})", ref):
            return search.group(1)
        if search := re.search(r"\d{19}", ref):
            return search.group(0)
    raise ValueError(f"ref {ref} Non conformance")


async def resolve_changdunovel(url: str) -> str:
    """解析 changdunovel.com URL，提取 book_id 返回标准 fanqienovel URL。

    优先直接从输入 URL 的 query params 提取 book_id（分享长链已包含）；
    兜底发请求跟随重定向提取 /t/ 短链。
    """
    if "changdunovel.com" not in url:
        return url
    # 优先直接从 URL query 提取（免网络请求）
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(url).query)
    bid = qs.get("book_id", [None])[0]
    if bid and bid.isdigit():
        return f"https://fanqienovel.com/page/{bid}"
    # 兜底：发请求跟随重定向提取 /t/ 短链（异步，不阻塞事件循环）
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            r = await client.get(url)
        qs = parse_qs(urlparse(str(r.url)).query)
        bid = qs.get("book_id", [None])[0]
        if bid and bid.isdigit():
            return f"https://fanqienovel.com/page/{bid}"
        book_id = standardize_id(str(r.url))
        return f"https://fanqienovel.com/page/{book_id}"
    except (httpx.HTTPError, ValueError):
        return url


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
                cover_url=book_info.get("thumb_url") or book_info.get("thumbUri") or None,
            ))

    return tuple(results)


def parse_novel_info(html: str) -> Novel:

    if BeautifulSoup(html, 'lxml').select_one("div.no-content"):
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
    # 封面只收集 URL，字节下载归 novel_info 能力函数（engine.async_fetch_images）
    cover_image = Illustration(raw_data=b"", alt=name, url=book_cover_url) if book_cover_url else None
    chapter_list_with_volume = json_data.get("page", {}).get("chapterListWithVolume", {})
    serial = 0
    for chapters_list in chapter_list_with_volume:
        serial += len(chapters_list)

    novel = Novel(url=book_url,
                  title=name,
                  author=author,
                  serial=serial,
                  tags=tuple(label_list),
                  description=abstract,
                  count=count_word,
                  cover=cover_image
                  )
    return novel


def parse_chapter_list(html: str) -> Chapters:

    if BeautifulSoup(html, 'lxml').select_one("div.no-content"):
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
                              id=standardize_id(chapter_url),
                              volume=volume_name,
                              order=order,
                              time=first_pass_time)
            chapter_list.append(chapter)

    return Chapters(chapter_list)


def parse_chapter_content(html: str, chapter: Chapter) -> tuple[Chapter, list[dict]] | None:
    """解析并填充 content/count；图片只收集 URL 元信息，由调用方统一下载。

    Returns:
        (chapter, img_urls) 二元组；img_urls 为 [{"url", "alt", "insert"}, ...]。
        页面存在 `div.muye-to-fanqie` 时返回 None。
    """

    if BeautifulSoup(html, 'lxml').select_one("div.no-content"):
        raise ChapterNotFoundError("Chapter page shows no-content div")
    if "window.__INITIAL_STATE__=" not in html:
        raise ParseError("Chapter page missing __INITIAL_STATE__")

    json_data = extract_json(html)
    if not json_data:
        raise ChapterNotFoundError("Chapter JSON extraction returned empty")
    count = json_data.get("reader", {}).get("chapterData", {}).get("chapterWordNumber")
    parent_soup = BeautifulSoup(html, 'lxml')
    if parent_soup.select_one('div.muye-to-fanqie'):
        return None

    html_content = str(parent_soup.select_one('div.muye-reader-content.noselect'))
    soup = BeautifulSoup(translate(html_content), 'lxml')

    content_div = soup.select_one('div.muye-reader-content.noselect')
    if not content_div:
        content_div = soup.select_one('div.muye-reader-content')

    separator = "\n\n"
    img_counter = 0
    img_tasks: list[dict] = []  # 收集图片下载任务，后面批量并发
    text_paragraphs: list[str] = []

    # 按直接子元素顺序遍历，同时提取文本和图片位置
    if content_div:
        inner = content_div.select_one('div')
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
                    img_tag = element.select_one('img')
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
                                    pic_desc_tag = parent.select_one('p.pictureDesc')
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
                img_tag = element.select_one('img')
                if img_tag:
                    img_counter += 1
                    group_id = img_counter

                    picture_desc = ""
                    pic_desc_tag = element.select_one('p.pictureDesc')
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

    # 图片只收集 URL 与插入位置，不下载字节（下载归 engine.async_fetch_images）
    img_urls: list[dict] = []
    for t in img_tasks:
        img_urls.append({"url": t["url"], "alt": t["alt"], "insert": t["insert"]})

    novel_content = separator.join(text_paragraphs)
    if '已经是最新一章' in novel_content:
        novel_content = novel_content.replace('已经是最新一章', '')

    chapter.count = count
    chapter.content = novel_content
    return chapter, img_urls
