import json
import os
import hmac
import hashlib
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

if not os.path.exists(CONFIG_PATH):
    raise SystemExit(
        "config.json not found. Copy server/config.example.json to server/config.json and fill it."
    )

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

BOT_TOKEN = CONFIG.get("bot_token", "").strip()
ADMIN_USERNAME = CONFIG.get("admin_username", "").strip().lstrip("@")
ADMIN_CHAT_ID = CONFIG.get("admin_chat_id")
WEBAPP_URL = CONFIG.get("webapp_url", "").strip()
LISTEN_HOST = CONFIG.get("listen_host", "0.0.0.0")
LISTEN_PORT = int(CONFIG.get("listen_port", 8080))
VERIFY_INIT_DATA = bool(CONFIG.get("verify_init_data", False))

if not BOT_TOKEN:
    raise SystemExit("bot_token is required in server/config.json")

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def api_request(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def resolve_admin_chat_id() -> Optional[int]:
    global ADMIN_CHAT_ID
    if ADMIN_CHAT_ID:
        return ADMIN_CHAT_ID
    if not ADMIN_USERNAME:
        return None
    result = api_request("getChat", {"chat_id": f"@{ADMIN_USERNAME}"})
    if result.get("ok"):
        ADMIN_CHAT_ID = result["result"]["id"]
        return ADMIN_CHAT_ID
    return None


def escape(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_payload(payload: Dict[str, Any]) -> str:
    kind = payload.get("type", "lead")
    header = "Новая заявка" if kind == "lead" else "Новый вопрос"
    lines = [f"<b>{header}</b>"]

    if payload.get("name"):
        lines.append(f"<b>Имя:</b> {escape(payload['name'])}")
    if payload.get("project"):
        lines.append(f"<b>Проект:</b> {escape(payload['project'])}")
    if payload.get("goal"):
        lines.append(f"<b>Цель:</b> {escape(payload['goal'])}")
    if payload.get("budget"):
        lines.append(f"<b>Бюджет:</b> {escape(payload['budget'])}")
    if payload.get("contact"):
        lines.append(f"<b>Контакт:</b> {escape(payload['contact'])}")
    if payload.get("message"):
        lines.append(f"<b>Сообщение:</b> {escape(payload['message'])}")

    user = payload.get("user") or {}
    if user:
        user_line = " ".join(
            part
            for part in [
                user.get("first_name"),
                user.get("last_name"),
                f"@{user.get('username')}" if user.get("username") else None,
                f"(id: {user.get('id')})" if user.get("id") else None,
            ]
            if part
        )
        if user_line:
            lines.append(f"<b>Пользователь:</b> {escape(user_line)}")

    if payload.get("created_at"):
        lines.append(f"<b>Время:</b> {escape(payload['created_at'])}")

    return "\n".join(lines)


def verify_init_data(init_data: str) -> bool:
    if not init_data:
        return False
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", "")
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items(), key=lambda item: item[0])
    )
    secret_key = hashlib.sha256(BOT_TOKEN.encode("utf-8")).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return calculated_hash == received_hash


def send_to_admin(payload: Dict[str, Any]) -> None:
    chat_id = resolve_admin_chat_id()
    if not chat_id:
        raise RuntimeError("Admin chat_id not resolved. Make sure admin started the bot.")
    text = format_payload(payload)
    api_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def answer_webapp_query(query_id: str, text: str) -> None:
    api_request(
        "answerWebAppQuery",
        {
            "web_app_query_id": query_id,
            "result": {
                "type": "article",
                "id": "lead",
                "title": "Заявка отправлена",
                "input_message_content": {"message_text": text},
            },
        },
    )


def handle_webapp_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    init_data = body.get("init_data", "")
    if VERIFY_INIT_DATA and not verify_init_data(init_data):
        return {"ok": False, "error": "init_data validation failed"}

    payload = body.get("payload") or {}
    if not payload:
        return {"ok": False, "error": "payload missing"}

    send_to_admin(payload)

    query_id = body.get("query_id")
    if query_id:
        answer_webapp_query(query_id, "Спасибо! Мы получили вашу заявку.")

    return {"ok": True}


def handle_telegram_update(update: Dict[str, Any]) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    text = message.get("text", "")
    if text.startswith("/start"):
        if not WEBAPP_URL:
            api_request(
                "sendMessage",
                {
                    "chat_id": message["chat"]["id"],
                    "text": "WebApp URL не настроен. Заполните webapp_url в config.json.",
                },
            )
            return
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": "Открыть приложение:",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "Открыть WebApp", "web_app": {"url": WEBAPP_URL}}]]
                },
            },
        )
        return

    web_app_data = message.get("web_app_data")
    if web_app_data and web_app_data.get("data"):
        try:
            payload = json.loads(web_app_data["data"])
        except json.JSONDecodeError:
            payload = {"type": "unknown", "message": web_app_data["data"]}
        send_to_admin(payload)
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": "Спасибо! Мы получили вашу заявку.",
            },
        )


class RequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return

        if self.path == "/webapp":
            result = handle_webapp_payload(body)
            status = 200 if result.get("ok") else 400
            self._send_json(status, result)
            return

        if self.path == "/telegram":
            handle_telegram_update(body)
            self._send_json(200, {"ok": True})
            return

        self._send_json(404, {"ok": False, "error": "not found"})


def main() -> None:
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), RequestHandler)
    print(f"Server running on http://{LISTEN_HOST}:{LISTEN_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
