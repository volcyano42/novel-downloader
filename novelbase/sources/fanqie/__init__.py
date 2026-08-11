import re

NAME = "fanqie"
SHOW_NAME = "番茄"
HOSTS = ("fanqienovel.com", "changdunovel.com")
ID_PATTERN = re.compile(r"^fanqie_(\d{19})$")
# 源站原始 ID（Novel.origin_id，去掉 {website}_ 前缀后的 ID）
ORIGIN_ID_PATTERN = re.compile(r"^\d{19}$")
# 构建书源完整 URL 的模板，{id} = ORIGIN_ID_PATTERN 匹配的部分
BOOK_URL_TEMPLATE = "https://fanqienovel.com/page/{id}"
