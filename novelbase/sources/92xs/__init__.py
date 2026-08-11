import re

NAME = "92xs"
SHOW_NAME = "就爱文学"
HOSTS = ("www.92xs.info", "92xs.info")
ID_PATTERN = re.compile(r"^92xs_(\d+)$")
# 源站原始 ID（Novel.origin_id，去掉 {website}_ 前缀后的 ID）
ORIGIN_ID_PATTERN = re.compile(r"^\d+$")
# 构建书源完整 URL 的模板，{id} = ORIGIN_ID_PATTERN 匹配的部分
BOOK_URL_TEMPLATE = "http://www.92xs.info/book/{id}.html"
