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

### 1) Настройка
Скопируйте пример и заполните:
```bash
cp /Users/daniilrylcev/Documents/New\ project\ 2/server/config.example.json \
   /Users/daniilrylcev/Documents/New\ project\ 2/server/config.json
```
В `server/config.json` заполните:
- `bot_token` — токен от @BotFather
- `admin_username` — юзернейм админа без `@`
- `webapp_url` — URL вашего WebApp
- `public_base_url` — публичный адрес сервера (HTTPS)

Важно: админ должен **написать боту /start**, иначе бот не сможет отправить ему сообщение.

### 2) Запуск сервера
```bash
python3 /Users/daniilrylcev/Documents/New\ project\ 2/server/bot_server.py
```
Сервер слушает `/webapp` (для WebApp) и `/telegram` (для webhook Telegram).

### 3) Настройка webhook
```bash
python3 /Users/daniilrylcev/Documents/New\ project\ 2/server/set_webhook.py
```

## Что происходит
- WebApp отправляет данные на `POST /webapp`
- Сервер пересылает заявку админу в личку
- Для inline‑кнопки бот отвечает пользователю через `answerWebAppQuery`
