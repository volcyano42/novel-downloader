import re

NAME = "92xs"
SHOW_NAME = "就爱文学"
HOSTS = ("www.92xs.info", "92xs.info")
ID_PATTERN = re.compile(r"^92xs_(\d+)$")
# 源站原始 ID（Novel.origin_id，去掉 {website}_ 前缀后的 ID）
ORIGIN_ID_PATTERN = re.compile(r"^\d+$")
