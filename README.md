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
- `webapp_url` — URL вашего WebApp
- `public_base_url` — публичный адрес сервера (HTTPS)

### 2) Настройка через env (для Render/Railway)
Можно не создавать `config.json`, а задать переменные окружения:
- `BOT_TOKEN`
- `ADMIN_USERNAME`
- `ADMIN_CHAT_ID` (опционально, рекомендовано)
- `WEBAPP_URL`
- `PUBLIC_BASE_URL`
- `PORT` (обычно выставляет сам хостинг)

Важно:
- админ должен написать боту `/start` (это привяжет chat_id по `admin_username`);
- можно получить chat_id командой `/myid` и сохранить его в `ADMIN_CHAT_ID`.

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
- Для inline‑кнопки бот отвечает пользователю через `answerWebAppQuery`
