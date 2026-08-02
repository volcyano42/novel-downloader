import re

NAME = "qimao"
SHOW_NAME = "七猫"
HOSTS = ("www.qimao.com",)
ID_PATTERN = re.compile(r"^qimao_(\d+)$")
# 源站原始 ID（Novel.origin_id，去掉 {website}_ 前缀后的 ID）
ORIGIN_ID_PATTERN = re.compile(r"^\d+$")
