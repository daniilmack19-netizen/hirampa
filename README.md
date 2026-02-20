# RAMPA WebApp

Статическая витрина + форма лидов для Telegram WebApp. Опубликованная версия — GitHub Pages.

## Конфиг WebApp (куда слать заявки)
Отредактируйте `/Users/daniilrylcev/Documents/New project 2/config.js`:
```js
window.APP_CONFIG = {
  backendUrl: "https://YOUR-BACKEND.example",
};
```

## Бот + сервер для заявок
Чтобы заявки уходили админу в личку, нужен небольшой сервер и бот.

### 1) Настройка через `config.json` (локально)
Скопируйте пример и заполните:
```bash
cp /Users/daniilrylcev/Documents/New\ project\ 2/server/config.example.json \
   /Users/daniilrylcev/Documents/New\ project\ 2/server/config.json
```
В `server/config.json` заполните:
- `bot_token` — токен от @BotFather
- `admin_username` — юзернейм админа без `@`
- `admin_chat_id` — опционально. Рекомендуется для стабильности после перезапусков.
- `strict_admin_check` — `true` (рекомендуется): для админ-доступа одновременно сверяются `admin_chat_id` и `admin_username`, если оба заданы.
- `webapp_url` — URL вашего WebApp
- `public_base_url` — публичный адрес сервера (HTTPS)
- `storage_path` — путь к JSON-хранилищу заявок
- `storage_retention_days` — через сколько дней удалять старые заявки
- `max_stored_items` — защитный лимит количества записей в JSON

### 2) Настройка через env (для Render/Railway)
Можно не создавать `config.json`, а задать переменные окружения:
- `BOT_TOKEN`
- `ADMIN_USERNAME`
- `ADMIN_CHAT_ID` (опционально, рекомендовано)
- `STRICT_ADMIN_CHECK` (`true/false`)
- `WEBAPP_URL`
- `PUBLIC_BASE_URL`
- `STORAGE_PATH`
- `STORAGE_RETENTION_DAYS`
- `MAX_STORED_ITEMS`
- `PORT` (обычно выставляет сам хостинг)

Важно:
- админ должен написать боту `/start` (это привяжет chat_id по `admin_username`);
- можно получить chat_id командой `/myid` и сохранить его в `ADMIN_CHAT_ID`.
- если админ отвечает реплаем на сообщение с заявкой, бот отправляет этот ответ клиенту в личку.

### 3) Запуск сервера
```bash
python3 /Users/daniilrylcev/Documents/New\ project\ 2/server/bot_server.py
```
Сервер слушает `/webapp` (для WebApp) и `/telegram` (для webhook Telegram).

### 4) Настройка webhook
```bash
python3 /Users/daniilrylcev/Documents/New\ project\ 2/server/set_webhook.py
```

## Что происходит
- WebApp отправляет данные на `POST /webapp`
- Сервер пересылает заявку админу в личку
- Бот сохраняет связку `admin_message_id -> client_chat_id` в JSON
- Админ отвечает реплаем на заявку, и бот отправляет этот текст клиенту
- Старые записи из JSON очищаются автоматически по `storage_retention_days`
- Для inline‑кнопки бот отвечает пользователю через `answerWebAppQuery`
