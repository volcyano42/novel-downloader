import re

NAME = "qidian"
SHOW_NAME = "起点"
HOSTS = ("www.qidian.com", "book.qidian.com")
ID_PATTERN = re.compile(r"^qidian_(\d{10})$")
# 源站原始 ID（Novel.origin_id，去掉 {website}_ 前缀后的 ID）
ORIGIN_ID_PATTERN = re.compile(r"^\d{10}$")
# 构建书源完整 URL 的模板，{id} = ORIGIN_ID_PATTERN 匹配的部分
BOOK_URL_TEMPLATE = "https://www.qidian.com/book/{id}/"
