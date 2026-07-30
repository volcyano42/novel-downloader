import re

NAME = "qidian"
HOSTS = ("www.qidian.com", "book.qidian.com")
ID_PATTERN = re.compile(r"^qidian_(\d{10})$")
