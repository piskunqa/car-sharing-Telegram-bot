import json
from os.path import join, dirname
from types import SimpleNamespace

# languages settings
DEFAULT_LANGUAGE = 'en'
START_COMMAND = 'Create a trip'
LANGUAGE_COMMAND = 'Change a language'
MENU_COMMAND = 'Show menu'
with open(join(dirname(__file__), "language.json"), "r", encoding="utf-8") as f:
    texts = (lambda o: SimpleNamespace(**{k: (lambda x: SimpleNamespace(
        **{kk: (lambda y: y if not isinstance(y, dict) else SimpleNamespace(**y))(vv) for kk, vv in
           v.items()}) if isinstance(v, dict) else v)(v) for k, v in o.items()}))(json.load(f)).__dict__

# directories settings
IMG_DIR = join(dirname(__file__), "images")

# database settings
DATABASE = "car_sharing"
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "9379992"

# bot settings
BOT_TOKEN = ''
REPORT_CHAT_ID = -5046315229
PLACES = range(1, 7)
TIMEPICKER_DEFAULT_OPTIONS = {"24hour": True, "minute_step": 5}

# admin panel settings
admin_user = "car_sharing_admin"
admin_secret_key = 'm6awtIc05xC0HPx7OjGkyY4RHDQJIddbfUN'
admin_password = '19kt2lAoFpBtXu3q4fSxyQwbYaI3wLvZlEF'
lock_by_ip, allow_ip_list = False, []

# routing settings
radius = 500
api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjVjOTc2YjZmZTI1OTQ5YWU5N2FkMzhmZjZlOGUwYjdhIiwiaCI6Im11cm11cjY0In0="
