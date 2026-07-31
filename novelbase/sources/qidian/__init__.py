import re

NAME = "qidian"
SHOW_NAME = "起点"
HOSTS = ("www.qidian.com", "book.qidian.com")
ID_PATTERN = re.compile(r"^qidian_(\d{10})$")
