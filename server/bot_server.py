import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

CONFIG: Dict[str, Any] = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)


def cfg(name: str, default: Any = "") -> Any:
    env_name = name.upper()
    if env_name in os.environ and os.environ[env_name] != "":
        return os.environ[env_name]
    return CONFIG.get(name, default)


def parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


BOT_TOKEN = str(cfg("bot_token", "")).strip()
ADMIN_USERNAME = str(cfg("admin_username", "")).strip().lstrip("@")
ADMIN_CHAT_ID = parse_optional_int(cfg("admin_chat_id"))
WEBAPP_URL = str(cfg("webapp_url", "")).strip()
LISTEN_HOST = str(cfg("listen_host", "0.0.0.0"))
LISTEN_PORT = int(os.getenv("PORT", cfg("listen_port", 8080)))
VERIFY_INIT_DATA = parse_bool(cfg("verify_init_data", "false"))
CORS_ORIGIN = str(cfg("cors_origin", "*")).strip() or "*"
STRICT_ADMIN_CHECK = parse_bool(cfg("strict_admin_check", "true"), default=True)
STORAGE_RETENTION_DAYS = max(
    1, parse_optional_int(cfg("storage_retention_days", 30)) or 30
)
MAX_STORED_ITEMS = max(100, parse_optional_int(cfg("max_stored_items", 3000)) or 3000)
_storage_path_raw = str(cfg("storage_path", "leads_store.json")).strip() or "leads_store.json"
if os.path.isabs(_storage_path_raw):
    STORAGE_PATH = _storage_path_raw
else:
    STORAGE_PATH = os.path.join(BASE_DIR, _storage_path_raw)

if not BOT_TOKEN:
    raise SystemExit("bot_token is required (env BOT_TOKEN or server/config.json)")

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_username(value: Any) -> str:
    return str(value or "").strip().lstrip("@").lower()


def make_storage_dir() -> None:
    directory = os.path.dirname(STORAGE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _empty_store() -> Dict[str, List[Dict[str, Any]]]:
    return {"items": []}


def cleanup_store(store: Dict[str, List[Dict[str, Any]]]) -> bool:
    items = store.get("items", [])
    cutoff = now_utc() - timedelta(days=STORAGE_RETENTION_DAYS)
    cleaned: List[Dict[str, Any]] = []
    changed = False
    for item in items:
        created_at = parse_iso_datetime(item.get("created_at")) or parse_iso_datetime(
            item.get("received_at")
        )
        if created_at is None or created_at < cutoff:
            changed = True
            continue
        cleaned.append(item)

    if len(cleaned) > MAX_STORED_ITEMS:
        cleaned = cleaned[-MAX_STORED_ITEMS:]
        changed = True

    if len(cleaned) != len(items):
        changed = True

    store["items"] = cleaned
    return changed


def save_store(store: Dict[str, List[Dict[str, Any]]]) -> None:
    make_storage_dir()
    with open(STORAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def load_store() -> Dict[str, List[Dict[str, Any]]]:
    if not os.path.exists(STORAGE_PATH):
        return _empty_store()
    try:
        with open(STORAGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _empty_store()

    if not isinstance(data, dict):
        return _empty_store()

    items = data.get("items")
    if not isinstance(items, list):
        items = []
    filtered_items = [item for item in items if isinstance(item, dict)]
    store: Dict[str, List[Dict[str, Any]]] = {"items": filtered_items}

    if cleanup_store(store):
        save_store(store)
    return store


def persist_request_mapping(admin_message: Dict[str, Any], payload: Dict[str, Any]) -> None:
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    client_chat_id = parse_optional_int(user.get("id"))
    if not client_chat_id:
        return

    created_at_dt = parse_iso_datetime(payload.get("created_at")) or now_utc()
    first_name = str(user.get("first_name") or "").strip()
    last_name = str(user.get("last_name") or "").strip()
    client_name = " ".join(part for part in [first_name, last_name] if part) or first_name or "-"

    item: Dict[str, Any] = {
        "id": f"{admin_message['chat']['id']}:{admin_message['message_id']}",
        "type": payload.get("type", "lead"),
        "created_at": to_iso(created_at_dt),
        "received_at": to_iso(now_utc()),
        "admin_chat_id": admin_message["chat"]["id"],
        "admin_message_id": admin_message["message_id"],
        "client_chat_id": client_chat_id,
        "client_username": str(user.get("username") or "").strip(),
        "client_name": client_name,
        "status": "new",
    }

    store = load_store()
    store["items"].append(item)
    cleanup_store(store)
    save_store(store)


def get_request_by_admin_message(
    admin_chat_id: int, admin_message_id: int
) -> Optional[Dict[str, Any]]:
    store = load_store()
    for item in reversed(store["items"]):
        if (
            item.get("admin_chat_id") == admin_chat_id
            and item.get("admin_message_id") == admin_message_id
        ):
            return item
    return None


def mark_request_as_answered(
    admin_chat_id: int, admin_message_id: int, reply_message_id: int
) -> None:
    store = load_store()
    for item in reversed(store["items"]):
        if (
            item.get("admin_chat_id") == admin_chat_id
            and item.get("admin_message_id") == admin_message_id
        ):
            item["status"] = "answered"
            item["answered_at"] = to_iso(now_utc())
            item["admin_reply_message_id"] = reply_message_id
            save_store(store)
            return


def is_admin_message(message: Dict[str, Any]) -> bool:
    from_user = message.get("from") or {}
    chat = message.get("chat") or {}
    username = normalize_username(from_user.get("username"))
    chat_id = parse_optional_int(chat.get("id"))

    checks: List[bool] = []
    if ADMIN_CHAT_ID is not None:
        checks.append(chat_id == ADMIN_CHAT_ID)
    if ADMIN_USERNAME:
        checks.append(username == ADMIN_USERNAME.lower())

    if not checks:
        return False
    if STRICT_ADMIN_CHECK:
        return all(checks)
    return any(checks)


def maybe_bind_admin_chat(message: Dict[str, Any]) -> None:
    global ADMIN_CHAT_ID
    if ADMIN_CHAT_ID is not None:
        return
    if not ADMIN_USERNAME:
        return
    from_user = message.get("from") or {}
    username = normalize_username(from_user.get("username"))
    if username != ADMIN_USERNAME.lower():
        return
    chat_id = parse_optional_int((message.get("chat") or {}).get("id"))
    if chat_id is not None:
        ADMIN_CHAT_ID = chat_id


def api_request(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            response = json.load(resp)
            if not response.get("ok", False):
                description = response.get("description", "unknown Telegram API error")
                raise RuntimeError(f"Telegram API {method} failed: {description}")
            return response
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
            description = parsed.get("description", body)
        except json.JSONDecodeError:
            description = body or str(error)
        raise RuntimeError(f"Telegram API {method} failed: {description}")


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

    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    if parse_optional_int(user.get("id")):
        lines.append("")
        lines.append("<i>Ответьте реплаем на это сообщение — бот отправит ответ клиенту.</i>")
    else:
        lines.append("")
        lines.append("<i>Автоответ недоступен: Telegram user id не получен.</i>")

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


def send_to_admin(payload: Dict[str, Any]) -> Dict[str, Any]:
    chat_id = resolve_admin_chat_id()
    if not chat_id:
        raise RuntimeError(
            "Admin chat_id not resolved. Set ADMIN_CHAT_ID (через /myid) and check ADMIN_USERNAME."
        )
    text = format_payload(payload)
    response = api_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )
    message = response.get("result") or {}
    if message.get("message_id") and message.get("chat"):
        persist_request_mapping(message, payload)
    return message


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

    try:
        send_to_admin(payload)
    except Exception as error:
        return {"ok": False, "error": str(error)}

    query_id = body.get("query_id")
    if query_id:
        try:
            answer_webapp_query(query_id, "Спасибо! Мы получили вашу заявку.")
        except Exception:
            # The lead is already delivered to admin; do not fail whole request.
            pass

    return {"ok": True}


def relay_admin_reply(message: Dict[str, Any]) -> bool:
    if not is_admin_message(message):
        return False

    reply_to = message.get("reply_to_message") or {}
    if not reply_to.get("message_id"):
        return False

    admin_text = (message.get("text") or message.get("caption") or "").strip()
    if not admin_text:
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": "Не отправлено: в ответе нет текста.",
            },
        )
        return True

    request_item = get_request_by_admin_message(
        admin_chat_id=message["chat"]["id"],
        admin_message_id=reply_to["message_id"],
    )
    if not request_item:
        return False

    client_chat_id = parse_optional_int(request_item.get("client_chat_id"))
    if not client_chat_id:
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": "Не удалось определить получателя заявки.",
            },
        )
        return True

    try:
        api_request(
            "sendMessage",
            {
                "chat_id": client_chat_id,
                "text": f"Ответ RAMPA по вашей заявке:\n\n{admin_text}",
            },
        )
        mark_request_as_answered(
            admin_chat_id=message["chat"]["id"],
            admin_message_id=reply_to["message_id"],
            reply_message_id=message["message_id"],
        )
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": "Ответ отправлен клиенту.",
            },
        )
    except Exception as error:
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": f"Не удалось отправить клиенту: {error}",
            },
        )
    return True


def handle_telegram_update(update: Dict[str, Any]) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    maybe_bind_admin_chat(message)

    from_user = message.get("from") or {}
    username = normalize_username(from_user.get("username"))

    text = message.get("text", "")
    if text.startswith("/myid"):
        admin_access = "yes" if is_admin_message(message) else "no"
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": (
                    f"chat_id: <code>{message['chat']['id']}</code>\\n"
                    f"username: @{username if username else '-'}\\n"
                    f"admin_bound: {'yes' if ADMIN_CHAT_ID else 'no'}\\n"
                    f"admin_access: {admin_access}"
                ),
                "parse_mode": "HTML",
            },
        )
        return

    if text.startswith("/start"):
        parts = []
        if is_admin_message(message):
            parts.append("Админ-чат привязан.")
        if not WEBAPP_URL:
            parts.append("WebApp URL не настроен. Заполните webapp_url.")
        else:
            parts.append("Открыть приложение:")
        response = {
            "chat_id": message["chat"]["id"],
            "text": "\\n".join(parts),
        }
        if WEBAPP_URL:
            response["reply_markup"] = {
                "inline_keyboard": [[{"text": "Открыть WebApp", "web_app": {"url": WEBAPP_URL}}]]
            }
        api_request("sendMessage", response)
        return

    if relay_admin_reply(message):
        return

    web_app_data = message.get("web_app_data")
    if web_app_data and web_app_data.get("data"):
        try:
            payload = json.loads(web_app_data["data"])
        except json.JSONDecodeError:
            payload = {"type": "unknown", "message": web_app_data["data"]}
        if isinstance(payload, dict) and from_user.get("id"):
            payload.setdefault("user", from_user)
        send_to_admin(payload)
        api_request(
            "sendMessage",
            {
                "chat_id": message["chat"]["id"],
                "text": "Спасибо! Мы получили вашу заявку.",
            },
        )


class RequestHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        try:
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
        except Exception as error:
            self._send_json(500, {"ok": False, "error": str(error)})


def main() -> None:
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), RequestHandler)
    print(f"Server running on http://{LISTEN_HOST}:{LISTEN_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
