# Bitrix Task Bot (Telegram -> Bitrix24)

Telegram-бот для создания задач в Bitrix24 через webhook. Бот ведет пользователя по диалогу (название -> описание -> вложения -> подтверждение), создает задачу в Bitrix и хранит привязку `Telegram ID -> Bitrix User ID` в SQLite.

## Что умеет

- Создавать задачи в Bitrix24 из Telegram (`/task` или кнопка «Создать задачу»).
- Привязывать профиль сотрудника Bitrix24 (`/link` или кнопка «Привязать профиль»).
- Проверять текущую привязку (`/me`).
- Ограничивать доступ по списку Telegram ID (`ALLOWED_TG_USERS`).
- Сохранять вложения от пользователя локально (фото/документы).
- Загружать вложения в Bitrix Disk и прикреплять их к задаче через `UF_TASK_WEBDAV_FILES`.
- Формировать ссылку на задачу в ответе после создания.

## Технологии

- Python 3.11+
- [python-telegram-bot 21.6](https://github.com/python-telegram-bot/python-telegram-bot)
- [httpx](https://www.python-httpx.org/)
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- SQLite (встроенный модуль `sqlite3`)

## Структура проекта

- `main.py` - точка входа, регистрация хендлеров Telegram.
- `bot_handlers.py` - диалоги и команды бота.
- `bitrix.py` - клиент Bitrix REST webhook.
- `config.py` - загрузка и валидация переменных окружения.
- `usermap.py` - SQLite-слой привязки Telegram <-> Bitrix.
- `linking.py` - helper-слой доступа к привязке.
- `storage.py` - пути и хранение вложений.
- `utils.py` - утилиты (ID тикета, имя файла, директории).
- `requirements.txt` - зависимости.

## Подготовка Bitrix24

1. Создайте входящий webhook в Bitrix24 с правами на задачи (и диск, если планируете подключать загрузку файлов в диск Bitrix).
2. Скопируйте webhook URL в формате вида:

```text
https://<portal>.bitrix24.ru/rest/<user_id>/<webhook_token>/
```

Важно: URL должен оканчиваться на `/`, иначе приложение завершится с ошибкой валидации.

## Установка и запуск

1. Создайте виртуальное окружение и установите зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Создайте файл `.env` в корне проекта.

3. Запустите бота:

```powershell
python main.py
```

## Конфигурация (.env)

Ниже полный список поддерживаемых переменных.

### Обязательные

- `TG_BOT_TOKEN` - токен Telegram-бота.
- `BITRIX_WEBHOOK_BASE` - базовый URL webhook Bitrix24 (обязательно с финальным `/`).
- `BITRIX_DEFAULT_RESPONSIBLE_ID` - `RESPONSIBLE_ID` по умолчанию для создаваемых задач.
- `BITRIX_DISK_FOLDER_ID` - ID папки Bitrix Disk для загрузки вложений перед созданием задачи.

### Опциональные

- `BITRIX_GROUP_ID` - группа/проект для задачи (`GROUP_ID`).
- `BITRIX_PRIORITY` - приоритет задачи (`PRIORITY`).
- `BITRIX_PORTAL_BASE` - базовый URL портала, используется для fallback-ссылки на задачу.
- `BITRIX_TASK_URL_TEMPLATE` - шаблон ссылки на задачу, например:
  - `https://yourportal.bitrix24.ru/company/personal/user/1/tasks/task/view/{task_id}/`
- `ALLOWED_TG_USERS` - CSV список Telegram ID, которым разрешен доступ.
  - Пример: `12345678,987654321`
  - Если пусто, доступ разрешен всем.
- `UPLOAD_DIR` - директория локального сохранения вложений (по умолчанию `./uploads`).
- `USERMAP_DB` - путь к SQLite БД привязок (по умолчанию `./data/users.db`).
- `BITRIX_HTTP_TIMEOUT` - таймаут обычных запросов к Bitrix API в секундах (по умолчанию `20`).
- `BITRIX_UPLOAD_TIMEOUT` - базовый таймаут upload-запросов в секундах (по умолчанию `90`).
- `BITRIX_UPLOAD_URL_TIMEOUT` - базовый таймаут uploadUrl-пути в секундах (по умолчанию `25`).
- `BITRIX_SMALL_UPLOAD_PROBE_TIMEOUT` - быстрый таймаут для ранних попыток `fileContent` на небольших файлах (по умолчанию `4`).
- `BITRIX_SMALL_UPLOAD_FINAL_TIMEOUT` - таймаут для финальной попытки (и `fileContent`, и `uploadUrl`) на небольших файлах (по умолчанию `5`).
- `BITRIX_UPLOAD_MAX_ATTEMPTS` - число попыток загрузки одного файла в Bitrix Disk (по умолчанию `4`).
- `BITRIX_UPLOAD_PARALLELISM` - сколько файлов загружать параллельно (по умолчанию `2`).
- `LOG_LEVEL` - уровень логирования (`INFO` по умолчанию).

### Пример `.env`

```env
TG_BOT_TOKEN=1234567890:AA...
BITRIX_WEBHOOK_BASE=https://yourportal.bitrix24.ru/rest/1/abcdef1234567890/
BITRIX_DEFAULT_RESPONSIBLE_ID=1
BITRIX_DISK_FOLDER_ID=1483465

BITRIX_GROUP_ID=10
BITRIX_PRIORITY=1

BITRIX_PORTAL_BASE=https://yourportal.bitrix24.ru
BITRIX_TASK_URL_TEMPLATE=https://yourportal.bitrix24.ru/company/personal/user/1/tasks/task/view/{task_id}/

ALLOWED_TG_USERS=12345678,87654321
UPLOAD_DIR=./uploads
USERMAP_DB=./data/users.db

BITRIX_HTTP_TIMEOUT=20
BITRIX_UPLOAD_TIMEOUT=90
BITRIX_UPLOAD_URL_TIMEOUT=25
BITRIX_SMALL_UPLOAD_PROBE_TIMEOUT=4
BITRIX_SMALL_UPLOAD_FINAL_TIMEOUT=5
BITRIX_UPLOAD_MAX_ATTEMPTS=4
BITRIX_UPLOAD_PARALLELISM=2

LOG_LEVEL=INFO
```

## Пользовательский сценарий

1. Пользователь отправляет `/start`.
2. Нажимает «Привязать профиль» и отправляет:
- либо ссылку на профиль вида `.../company/personal/user/123/`
- либо просто число `123`
3. Нажимает «Создать задачу» (или `/task`).
4. Вводит название, затем описание.
5. Прикладывает файлы/скриншоты (опционально), затем нажимает «Готово».
6. Подтверждает создание.
7. Бот создает задачу в Bitrix и возвращает `ID` (и ссылку, если настроена).

## Команды

- `/start` - показать меню.
- `/task` - запустить диалог создания задачи.
- `/link` - запустить диалог привязки Bitrix-профиля.
- `/me` - показать текущие `TG ID` и привязанный `Bitrix ID`.
- `/cancel` - отменить текущий диалог.

## Хранение данных

- Привязка пользователей хранится в SQLite: `USERMAP_DB`.
- Таблица: `tg_bitrix_map (tg_id, bitrix_user_id, linked_at)`.
- Вложения сохраняются локально в структуре:

```text
UPLOAD_DIR/YYYY-MM-DD/<tg_id>/<ticket_id>/...
```

## Важные детали реализации

- Бот не создает задачи без привязки профиля Bitrix.
- `CREATED_BY` берется из привязки пользователя; если Bitrix отклоняет этот параметр, есть fallback-попытка создания без него.
- Вложения сначала сохраняются локально, затем загружаются в Bitrix Disk (`disk.folder.uploadfile`) в папку `BITRIX_DISK_FOLDER_ID`.
- При нескольких вложениях загрузка выполняется с ограниченной параллельностью (настраивается через `BITRIX_UPLOAD_PARALLELISM`), чтобы сократить общее время.
- При создании задачи вложения передаются в `UF_TASK_WEBDAV_FILES` в формате `n<file_id>`.
- Локальные пути вложений не добавляются в описание задачи (чтобы не засорять текст).
- Для небольших файлов используется быстрый путь загрузки (`fileContent`), при сбоях есть fallback на `uploadUrl`.
- Количество попыток и upload-таймауты настраиваются через `BITRIX_UPLOAD_MAX_ATTEMPTS`, `BITRIX_SMALL_UPLOAD_PROBE_TIMEOUT` и `BITRIX_SMALL_UPLOAD_FINAL_TIMEOUT`.
- Ограничения вложений: до 10 файлов на задачу, до 20 MB на один файл.
- Если пользователь приложил файлы и не загрузился ни один, задача не создается.
- Если загрузилась только часть файлов, задача создается с успешными вложениями, а бот показывает список неуспешных.

## Troubleshooting

- Ошибка `TG_BOT_TOKEN is required`:
  - Проверьте, что `.env` лежит в корне проекта и содержит `TG_BOT_TOKEN`.

- Ошибка `BITRIX_WEBHOOK_BASE must end with '/'`:
  - Добавьте завершающий `/` в URL webhook.

- Ошибка `BITRIX_DISK_FOLDER_ID is required`:
  - Добавьте `BITRIX_DISK_FOLDER_ID` в `.env` (целочисленный ID папки Bitrix Disk).

- Бот пишет «Доступ запрещён»:
  - Проверьте `ALLOWED_TG_USERS` и ваш Telegram ID (`/me`).

- Бот не дает создать задачу и просит привязать профиль:
  - Выполните `/link` и отправьте корректный URL профиля или ID пользователя Bitrix.

- Задача создалась, но нет ссылки:
  - Заполните `BITRIX_TASK_URL_TEMPLATE` или `BITRIX_PORTAL_BASE`.

- Бот сообщает, что вложения не загрузились и задача не создана:
  - Проверьте, что `BITRIX_DISK_FOLDER_ID` существует, webhook имеет права на Disk, и папка доступна пользователю webhook.

- Вложения иногда загружаются долго или нестабильно:
  - Проверьте сетевую доступность портала Bitrix24 с сервера, прокси/WAF и лимиты REST API.

## Разработка

Локальный запуск для разработки:

```powershell
python main.py
```

Полезно включить подробные логи:

```env
LOG_LEVEL=DEBUG
```

## Безопасность

- Не коммитьте `.env` и webhook токены.
- Ограничьте `ALLOWED_TG_USERS` для production-окружения.
- Регулярно ротируйте webhook-ключи в Bitrix24.
