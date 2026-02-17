import json
import os
import urllib.request

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

if not os.path.exists(CONFIG_PATH):
    raise SystemExit("config.json not found. Copy server/config.example.json to server/config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

bot_token = config.get("bot_token", "").strip()
public_base_url = config.get("public_base_url", "").strip().rstrip("/")

if not bot_token or not public_base_url:
    raise SystemExit("bot_token and public_base_url are required in server/config.json")

webhook_url = f"{public_base_url}/telegram"

req = urllib.request.Request(
    f"https://api.telegram.org/bot{bot_token}/setWebhook",
    data=f"url={webhook_url}".encode("utf-8"),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)

with urllib.request.urlopen(req, timeout=10) as resp:
    print(resp.read().decode("utf-8"))
