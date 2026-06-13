import json
import re
import time
from typing import Sequence

import requests
from bs4 import BeautifulSoup, Tag
from yarl import URL

from .base import BaseParser
from ..core.exceptions import AntiCrawlError, ChapterNotFoundError, FeatureNotSupportedError, NovelNotFoundError
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, SearchResult, Illustration, Chapters
from ..utils.logger import get_logger

_log = get_logger("nldlder.parsers.fanqie")

# 小说内容转码表
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

# 搜索页面的转码表
search_transcoding = {'58422': '0', '58400': '1', '58646': '2', '58381': '3', '58355': '4', '58707': '5', '58530': '6',
                      '58538': '7', '58685': '8', '58415': '9', '58614': 'a', '58620': 'b', '58487': 'c', '58452': 'd',
                      '58674': 'e', '58535': 'f', '58406': 'g', '58375': 'h', '58601': 'i', '58498': 'j', '58708': 'k',
                      '58475': 'l', '58514': 'm', '58700': 'n', '58606': 'o', '58650': 'p', '58582': 'q', '58659': 'r',
                      '58345': 's', '58709': 't', '58407': 'u', '58474': 'v', '58376': 'w', '58546': 'x', '58529': 'y',
                      '58494': 'z', '58476': 'A', '58353': 'B', '58622': 'C', '58594': 'D', '58531': 'E', '58590': 'F',
                      '58389': 'G', '58675': 'H', '58607': 'I', '58508': 'J', '58393': 'K', '58460': 'L', '58412': 'M',
                      '58403': 'N', '58473': 'O', '58453': 'P', '58704': 'Q', '58519': 'R', '58466': 'S', '58658': 'T',
                      '58356': 'U', '58525': 'V', '58548': 'W', '58570': 'X', '58497': 'Y', '58409': 'Z', '58454': '的',
                      '58549': '一', '58484': '是', '58504': '了', '58581': '我', '58656': '不', '58578': '人',
                      '58349': '在', '58350': '他', '58711': '有', '58694': '这', '58587': '个', '58534': '上',
                      '58360': '们', '58465': '来', '58547': '到', '58600': '时', '58643': '大', '58706': '地',
                      '58568': '为', '58495': '子', '58380': '中', '58644': '你', '58405': '说', '58551': '生',
                      '58471': '国', '58378': '年', '58631': '着', '58490': '就', '58513': '那', '58647': '和',
                      '58386': '要', '58633': '她', '58640': '出', '58591': '也', '58488': '得', '58469': '里',
                      '58563': '后', '58479': '自', '58565': '以', '58712': '会', '58598': '家', '58518': '可',
                      '58702': '下', '58562': '而', '58496': '过', '58673': '天', '58612': '去', '58351': '能',
                      '58586': '对', '58561': '小', '58372': '多', '58610': '然', '58383': '于', '58477': '心',
                      '58576': '学', '58501': '么', '58575': '之', '58696': '都', '58485': '好', '58639': '看',
                      '58690': '起', '58599': '发', '58605': '当', '58511': '没', '58550': '成', '58653': '只',
                      '58526': '如', '58688': '事', '58683': '把', '58596': '还', '58698': '用', '58446': '第',
                      '58651': '样', '58445': '道', '58541': '想', '58347': '作', '58489': '种', '58556': '开',
                      '58411': '美', '58663': '总', '58671': '从', '58480': '无', '58617': '情', '58398': '己',
                      '58390': '面', '58655': '最', '58449': '女', '58554': '但', '58522': '现', '58470': '前',
                      '58472': '些', '58502': '所', '58388': '同', '58560': '日', '58693': '手', '58703': '又',
                      '58413': '行', '58491': '意', '58368': '动', '58392': '方', '58408': '期', '58440': '它',
                      '58687': '头', '58521': '经', '58539': '长', '58459': '儿', '58463': '回', '58574': '位',
                      '58391': '分', '58664': '爱', '58615': '老', '58597': '因', '58533': '很', '58414': '给',
                      '58505': '名', '58699': '法', '58436': '间', '58520': '斯', '58668': '知', '58402': '世',
                      '58394': '什', '58418': '两', '58377': '次', '58444': '使', '58665': '身', '58367': '者',
                      '58588': '被', '58363': '高', '58448': '已', '58616': '亲', '58369': '其', '58657': '进',
                      '58427': '此', '58542': '话', '58434': '常', '58649': '与', '58366': '活', '58359': '正',
                      '58637': '感', '58438': '见', '58524': '明', '58462': '问', '58627': '力', '58624': '理',
                      '58365': '尔', '58691': '点', '58416': '文', '58567': '几', '58435': '定', '58397': '本',
                      '58613': '公', '58382': '特', '58660': '做', '58410': '外', '58439': '孩', '58641': '相',
                      '58537': '西', '58713': '果', '58527': '走', '58417': '将', '58536': '月', '58384': '十',
                      '58635': '实', '58425': '向', '58362': '声', '58516': '车', '58364': '全', '58552': '信',
                      '58585': '重', '58566': '三', '58545': '机', '58634': '工', '58630': '物', '58433': '气',
                      '58515': '每', '58352': '并', '58589': '别', '58692': '真', '58432': '打', '58619': '太',
                      '58652': '新', '58608': '比', '58358': '才', '58654': '便', '58540': '夫', '58395': '再',
                      '58592': '书', '58512': '部', '58447': '水', '58426': '像', '58510': '眼', '58401': '等',
                      '58618': '体', '58486': '却', '58670': '加', '58623': '电', '58370': '主', '58697': '界',
                      '58523': '门', '58714': '利', '58544': '海', '58507': '受', '58677': '听', '58499': '表',
                      '58604': '德', '58430': '少', '58357': '克', '58483': '代', '58572': '员', '58419': '许',
                      '58593': '稜', '58492': '先', '58348': '口', '58679': '由', '58571': '死', '58429': '安',
                      '58595': '写', '58457': '性', '58559': '马', '58482': '光', '58428': '白', '58602': '或',
                      '58603': '住', '58695': '难', '58373': '望', '58396': '教', '58528': '命', '58437': '花',
                      '58399': '结', '58583': '乐', '58636': '色', '58628': '更', '58629': '拉', '58558': '东',
                      '58464': '神', '58638': '记', '58701': '处', '58682': '让', '58662': '母', '58555': '父',
                      '58424': '应', '58441': '直', '58361': '字', '58678': '场', '58478': '平', '58371': '报',
                      '58421': '友', '58456': '关', '58374': '放', '58689': '至', '58420': '张', '58569': '认',
                      '58503': '接', '58705': '告', '58385': '入', '58553': '笑', '58557': '内', '58423': '英',
                      '58481': '军', '58645': '侯', '58715': '民', '58710': '岁', '58669': '往', '58431': '何',
                      '58517': '度', '58450': '山', '58609': '觉', '58642': '路', '58564': '带', '58621': '万',
                      '58387': '男', '58681': '边', '58442': '风', '58451': '解', '58458': '叫', '58684': '任',
                      '58506': '金', '58680': '快', '58632': '原', '58611': '吃', '58461': '妈', '58543': '变',
                      '58455': '通', '58666': '师', '58493': '立', '58584': '象', '58443': '数', '58468': '四',
                      '58626': '失', '58509': '满', '58532': '战', '58577': '远', '58661': '格', '58354': '士',
                      '58579': '音', '58667': '轻', '58573': '目', '58686': '条', '58580': '呢'}


def translate(en_text: str | None, coding=0) -> str:
    if not en_text: return ''
    de_text = ''
    if not coding:
        transcoding = content_transcoding
    else:
        transcoding = search_transcoding
    for index in en_text:
        t1 = ''
        try:
            t1 = transcoding[str(ord(index))]
        except KeyError:
            t1 = index
        finally:
            de_text += t1
    return de_text

def user_status(html):
    soup = BeautifulSoup(html, 'lxml')
    user_info_div = soup.find("div", class_="muye-header-right")
    if user_info_div:
        if user_info_div.find('img'):  # 有图片证明已登录
            user_state_code = 0
        else:
            user_state_code = -1
        if user_info_div.find('i', class_='user-content-vip'):  # 有vip图标时
            user_state_code = 1
    else:
        user_state_code = -1
    return user_state_code


def extract_json(html_content: str):
    start = html_content.find("window.__INITIAL_STATE__=") + len("window.__INITIAL_STATE__=")
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


# 通过html获取小说相关信息的基类
class FanqieHTMLParser(BaseParser):

    @staticmethod
    def can_handle(identifier: str | int) -> bool:
        pass

    def login(self, engine, **kwargs) -> AuthCredential:
        pass

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        results: list[SearchResult] = []
        offset = page * 10
        search_url = f"https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/?aid=1967&offset=0&q={search_ref}"
        try:
            content = requests.get(search_url).json()
        except Exception:
            _log.warning("search API failed")
            return None
        if content.get("data") and content["data"].get("ret_data"):
            for book_info in content["data"]["ret_data"]:
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
        return tuple(results) if results else None

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        if BeautifulSoup(novel_ref, 'lxml').find("div", class_="no-content"):
            raise NovelNotFoundError()
        json_data = extract_json(novel_ref)
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
        except Exception:
            book_cover_data = b""
        cover_image = Illustration(raw_data=book_cover_data, alt= name, url=book_cover_url)
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

    def parse_chapter_list(self, novel_ref: str, engine, **kwargs) -> tuple[Chapter, ...]:

        if BeautifulSoup(novel_ref, 'lxml').find("div", class_="no-content"):
            raise ChapterNotFoundError("Chapter list not found")
        json_data = extract_json(novel_ref)
        chapter_list_with_volume = json_data.get("page").get("chapterListWithVolume")
        book_url = "https://fanqienovel.com/page/" + json_data.get("page", {}).get("bookId")
        chapter_list = []
        for chapters_list in chapter_list_with_volume:
            for chapter_item in chapters_list:
                title = chapter_item["title"]
                chapter_url = 'https://fanqienovel.com/reader/' + chapter_item.get("itemId")
                first_pass_time = int(chapter_item.get("firstPassTime"))
                order = int(chapter_item.get("realChapterOrder"))
                volume_name = chapter_item.get("volume_name")
                chapter = Chapter(title=title,
                                  url=chapter_url,
                                  index_url=book_url,
                                  id = standardize_id(chapter_url),
                                  volume=volume_name,
                                  order=order,
                                  time=first_pass_time)
                chapter_list.append(chapter)

        return tuple(chapter_list)

    def parse_chapter_content(self, chapter_ref: str, engine, **kwargs) -> Chapter:
        """解析并填充content, count, images, is_complete"""

        chapter: Chapter = kwargs["chapter"]
        # 定位json起始和终点位置
        if BeautifulSoup(chapter_ref, 'lxml').find("div", class_="no-content"):
            raise ChapterNotFoundError("Chapter content not found")
        if "window.__INITIAL_STATE__=" not in chapter_ref:
            raise AntiCrawlError("Chapter content not found")

        json_data = extract_json(chapter_ref)
        count = json_data.get("reader", {}).get("chapterData", {}).get("chapterWordNumber")
        parent_soup = BeautifulSoup(chapter_ref, 'lxml')
        if parent_soup.find('div', class_='muye-to-fanqie'):
            is_complete = False
        else:
            is_complete = True
        # 减小范围以准确定位text和img
        html_content = str(parent_soup.find('div', class_='muye-reader-content noselect'))
        soup = BeautifulSoup(translate(html_content), 'lxml')

        # 定位内容容器
        content_div = soup.find('div', class_='muye-reader-content noselect')
        if not content_div:
            content_div = soup.find('div', class_='muye-reader-content')

        SEPARATOR = "\n\n"
        img_counter = 0
        img_items: list[Illustration] = []
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
                            picdesc_p = element.find_next_sibling('p', class_='pictureDesc')
                            if not picdesc_p:
                                parent = element.parent
                                while parent and isinstance(parent, Tag):
                                    if parent.name == 'div' and parent.get('data-fanqie-type') == 'image':
                                        picdesc_tag = parent.find('p', class_='pictureDesc')
                                        if picdesc_tag and isinstance(picdesc_tag, Tag):
                                            if picdesc_tag.get('group-id') == str(group_id):
                                                picture_desc = picdesc_tag.get_text(strip=True)
                                        break
                                    if parent.name == 'p' and 'pictureDesc' in (parent.get('class') or []):
                                        picture_desc = parent.get_text(strip=True)
                                        break
                                    parent = parent.parent
                            else:
                                if picdesc_p.get('group-id') == str(group_id):
                                    picture_desc = picdesc_p.get_text(strip=True)

                            img_url = img_tag.get('src', '')
                            if isinstance(img_url, list):
                                img_url = img_url[0] if img_url else None
                            if isinstance(img_url, str) and img_url.strip():
                                try:
                                    img_data = requests.get(img_url, timeout=10).content
                                except Exception:
                                    img_data = b""
                                prefix = SEPARATOR.join(text_paragraphs)
                                insert_pos = len(prefix) if text_paragraphs else 0
                                chapter_img = Illustration(
                                    alt=picture_desc, raw_data=img_data,
                                    insert=insert_pos, url=img_url
                                )
                                img_items.append(chapter_img)
                        continue

                    if 'pictureDesc' in cls:
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
                        picdesc_tag = element.find('p', class_='pictureDesc')
                        if picdesc_tag and isinstance(picdesc_tag, Tag):
                            if picdesc_tag.get('group-id') == str(group_id):
                                picture_desc = picdesc_tag.get_text(strip=True)

                        img_url = img_tag.get('src', '')
                        if isinstance(img_url, list):
                            img_url = img_url[0] if img_url else None
                        if isinstance(img_url, str) and img_url.strip():
                            try:
                                img_data = requests.get(img_url, timeout=10).content
                            except Exception:
                                img_data = b""
                            prefix = SEPARATOR.join(text_paragraphs)
                            insert_pos = len(prefix) if text_paragraphs else 0
                            chapter_img = Illustration(
                                alt=picture_desc, raw_data=img_data,
                                insert=insert_pos, url=img_url
                            )
                            img_items.append(chapter_img)

        novel_content = SEPARATOR.join(text_paragraphs)
        if '已经是最新一章' in novel_content:
            novel_content = novel_content.replace('已经是最新一章', '')

        chapter.count = count
        chapter.content = novel_content
        chapter.images = tuple(img_items)
        chapter.is_complete = is_complete
        # 赋值
        return chapter

class FanqieBrowserParser(FanqieHTMLParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        pass

    def login(self, engine, **credentials) -> AuthCredential:
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

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        _log.debug("parse_search_info: ref=%s page=%s", search_ref, page)
        return super().parse_search_info(search_ref=search_ref, engine=engine, page=page, **kwargs)

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:

        url = f"https://fanqienovel.com/page/{standardize_id(novel_ref)}"
        html = engine.fetch_text(url=url)
        novel = super().parse_novel_info(novel_ref=html, engine=engine, **kwargs)
        return novel

    def parse_chapter_list(self, novel_ref: Novel, engine, **kwargs) -> Chapters:
        url = f"https://fanqienovel.com/page/{standardize_id(novel_ref)}"
        html = engine.fetch_text(url=url)
        chapter_list = super().parse_chapter_list(novel_ref=html, engine=engine, **kwargs)
        return Chapters(chapter_list)

    def parse_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        url = f"https://fanqienovel.com/reader/{standardize_id(chapter_ref[0])}"
        html = engine.fetch_text(url=url)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError("chapter content not found")
        chapter = super().parse_chapter_content(chapter_ref=html, engine=engine, chapter = chapter_ref[0], **kwargs)
        return Chapters(chapter)

class FanqieOIAPIParser(BaseParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        pass

    def login(self, engine, **kwargs) -> None:
        raise FeatureNotSupportedError("login", f"Not Supported login by the API")

    @staticmethod
    def parse_search_info(search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        results: list[SearchResult] = []
        post_data = {
            "page": page,
            "keyword": search_ref,
            "key": engine.options.key,
            "method": "search",
            "type": "json"
        }
        content = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data)
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
        return tuple(results) if results else None

    @staticmethod
    def parse_novel_info(novel_ref: str, engine, **kwargs) -> Novel:

        novel_id = standardize_id(novel_ref)
        post_data = {
            "chapter": 0,
            "id": novel_id,
            "key": engine.options.key,
            "type": "json"
        }
        json_data = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data)
        data = json_data.get('data')
        if not data:
            raise NovelNotFoundError()
        else:
            serial = data.get("serial")
            url = f"https://fanqienovel.com/page/{data.get('id')}"
            book_cover_url = data.get('thumb')
            try:
                book_cover_data = requests.get(book_cover_url, timeout=10).content
            except Exception:
                book_cover_data = b""
            name = data.get('title')
            novel_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)
            author = data.get('author')
            word_number = int(data.get('word_number'))
            # 更新小说信息
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

    @staticmethod
    def parse_chapter_list(novel_ref: Novel, engine, **kwargs) -> Chapters:

        novel_id = standardize_id(novel_ref)
        post_data = {
            "id": novel_id,
            "key": engine.options.key,
            "method": "chapters",
            "type": "json"
        }
        json_data = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data)
        chapter_items_volume = json_data.get('data')
        if not chapter_items_volume:
            raise ChapterNotFoundError("Chapter list not found")
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
                    index_url=novel_ref.url,
                    volume=volume_name,
                    time=timestamp
                )
                results.append(chapter)
        return Chapters(results)

    @staticmethod
    def parse_chapter_content(
            chapter_ref: Sequence[Chapter],
            engine,
            **kwargs
    ) -> Chapters:
        """解析并填充content, count, is_complete(True)"""
        novel_url = chapter_ref[0].index_url
        chapter_ref = sorted(chapter_ref, key=lambda chapter: chapter.order)
        novel_id = standardize_id(novel_url)
        orders = ",".join([str(chapter.order) for chapter in chapter_ref])
        post_data = {
            "id": novel_id,
            "chapter": orders,
            "key": engine.options.key,
            "method": "chapter",
            "type": "json"
        }
        response = engine.fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data)
        data_list = response.get('data')
        if data_list is None:
            message = response.get('message',"")
            if message == "请检测章节选择是否正确":
                raise ChapterNotFoundError(message=f"Invalid chapter order: {orders}")
            elif message == "实例化失败: Trying to access array offset on value of type bool line 197in api.php":
                raise AntiCrawlError("requests too busy")
            else:
                raise ChapterNotFoundError(message=f"The API did not return the expected data")
        for idx, data in enumerate(sorted(data_list, key=lambda item: item["chapter"])):
            title = data['chapter_title']
            content = data['content'].replace(f"{title}\n\n","")
            chapter = chapter_ref[idx]
            chapter.content = content
            chapter.count = data['word_number']
            chapter.is_complete = True
        return Chapters(chapter_ref)

class FanqieRainParser(BaseParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        pass

    def login(self, engine, **kwargs) -> None:
        raise FeatureNotSupportedError("login", f"Not Supported login by the Rain API")

    @staticmethod
    def _api_url(engine, **params) -> str:
        key = engine.options.key
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://v3.rain.ink/fanqie/?apikey={key}&{qs}"

    @staticmethod
    def parse_search_info(search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        results: list[SearchResult] = []
        offset = page * 10
        url = FanqieRainParser._api_url(engine, type=1, keywords=search_ref, page=offset)
        content = engine.fetch_json(url)

        if content.get("code") != 0 and str(content.get("code")) != "0":
            return None

        books = None
        if "search_tabs" in content:
            for tab in content["search_tabs"]:
                if tab.get("data") is not None:
                    books = tab["data"]
                    break
        if books is None:
            books = content.get("data")

        if not books or not isinstance(books, list):
            return None

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
        return tuple(results) if results else None

    @staticmethod
    def parse_novel_info(novel_ref: str, engine, **kwargs) -> Novel:

        novel_id = standardize_id(novel_ref)
        url = FanqieRainParser._api_url(engine, type=2, bookid=novel_id)
        json_data = engine.fetch_json(url)

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
        except Exception:
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

    @staticmethod
    def parse_chapter_list(novel_ref: Novel, engine, **kwargs) -> Chapters:

        novel_id = standardize_id(novel_ref)
        url = FanqieRainParser._api_url(engine, type=3, bookid=novel_id)
        json_data = engine.fetch_json(url)

        if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
            raise ChapterNotFoundError("Chapter list not found")

        item_data_list = json_data.get("data", {}).get("item_data_list")
        if not item_data_list:
            raise ChapterNotFoundError("Chapter list not found")

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
                index_url=novel_ref.url,
                volume=volume_name,
                time=first_pass_time,
            )
            results.append(chapter)
        return Chapters(results)

    @staticmethod
    def parse_chapter_content(
            chapter_ref: Sequence[Chapter],
            engine,
            **kwargs
    ) -> Chapters:
        """解析并填充content, count, is_complete(True)"""
        novel_url = chapter_ref[0].index_url
        chapter_ref = sorted(chapter_ref, key=lambda chapter: chapter.order)

        for idx, chapter in enumerate(chapter_ref):
            item_id = standardize_id(chapter)
            url = FanqieRainParser._api_url(engine, type=4, itemid=item_id)
            response = engine.fetch_json(url)

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
            chapter.is_complete = True

        return Chapters(chapter_ref)

class FanqieRequestsParser(FanqieHTMLParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        pass

    def login(self, engine, **kwargs) -> None:
        raise FeatureNotSupportedError("login", f"Not Supported login by the Requests")

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        _log.debug("parse_search_info: ref=%s page=%s", search_ref, page)
        return super().parse_search_info(search_ref=search_ref, engine=engine, page=page, **kwargs)

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        url = f"https://fanqienovel.com/page/{standardize_id(novel_ref)}"
        html = engine.fetch_text(url=url)
        novel = super().parse_novel_info(novel_ref=html, engine=engine, **kwargs)
        return novel

    def parse_chapter_list(self, novel_ref: Novel, engine, **kwargs) -> Chapters:
        url = f"https://fanqienovel.com/page/{standardize_id(novel_ref)}"
        html = engine.fetch_text(url=url)
        chapter_list = super().parse_chapter_list(novel_ref=html, engine=engine, **kwargs)
        return Chapters(chapter_list)

    def parse_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        url = f"https://fanqienovel.com/reader/{standardize_id(chapter_ref[0])}"
        html = engine.fetch_text(url=url)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError(chapter_ref[0].url)
        chapter = super().parse_chapter_content(chapter_ref=html, engine=engine, chapter = chapter_ref[0], **kwargs)
        return Chapters(chapter)

def use_parser(engine) -> type[FanqieRequestsParser] | type[FanqieBrowserParser] | type[FanqieOIAPIParser] | type[FanqieRainParser]:
    if engine.name == "browser":
        return FanqieBrowserParser
    elif engine.name == "requests":
        return FanqieRequestsParser
    elif engine.name == "API":
        api_name = engine.options.name
        if api_name is None or api_name == "oiapi":
            return FanqieOIAPIParser
        if api_name == "rain":
            return FanqieRainParser
        raise ValueError(
            f"Unsupported API backend: {api_name!r}. "
            f"Only 'oiapi' and 'rain' are supported."
        )
    else:
        raise ValueError(f"Unknown engine: {engine.name}")


class FanqieParser(BaseParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        try:
            standardize_id(identifier)
            if URL(identifier).host in ("fanqienovel.com", "changdunovel.com"):
                return True
        finally:pass
        return False

    def login(self, engine, **kwargs) -> AuthCredential | None:
        parser = use_parser(engine=engine)()
        return parser.login(engine=engine, **kwargs)

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page=0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        parser = use_parser(engine=engine)()
        return parser.parse_search_info(search_ref=search_ref, engine=engine, page=page, **kwargs)

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        parser = use_parser(engine=engine)()
        return parser.parse_novel_info(novel_ref=novel_ref, engine=engine, **kwargs)

    def parse_chapter_list(self, novel_ref: Novel, engine, **kwargs) -> Chapters:
        parser = use_parser(engine=engine)()
        return parser.parse_chapter_list(novel_ref=novel_ref, engine=engine, **kwargs)

    def parse_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        parser = use_parser(engine=engine)()
        chapters = parser.parse_chapter_content(chapter_ref=chapter_ref, engine=engine, **kwargs)
        return chapters