import re

NAME = "fanqie"
SHOW_NAME = "番茄"
HOSTS = ("fanqienovel.com", "changdunovel.com")
ID_PATTERN = re.compile(r"^fanqie_(\d{19})$")
# 源站原始 ID（Novel.origin_id，去掉 {website}_ 前缀后的 ID）
ORIGIN_ID_PATTERN = re.compile(r"^\d{19}$")
