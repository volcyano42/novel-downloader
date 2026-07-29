import re

NAME = "fanqie"
HOSTS = ("fanqienovel.com", "changdunovel.com")
ID_PATTERN = re.compile(r"^(?:book_id=?)?(\d{19})$")
