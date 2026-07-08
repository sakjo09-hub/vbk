# Virtual Betting API

Платформа для тренировки спортивной аналитики на **виртуальной валюте** (без реальных денег).
Пользователи регистрируются, получают стартовый баланс, делают ставки на спортивные события
(футбол, Dota 2) по коэффициентам, а после матча система автоматически рассчитывает выигрыши.

## Стек

- **FastAPI** — асинхронный REST API
- **SQLAlchemy 2.0 (async) + asyncpg** — работа с PostgreSQL
- **Alembic** — миграции БД
- **Pydantic v2 / pydantic-settings** — валидация и конфиг
- **python-jose + passlib[bcrypt]** — JWT-аутентификация
- **httpx + BeautifulSoup4/lxml** — парсинг страниц БК
- **APScheduler** — фоновый импорт событий и расчёт результатов

## Структура

```
betting_project/
├── app/
│   ├── main.py              # точка входа FastAPI
│   ├── config.py            # настройки (.env)
│   ├── database.py          # async engine + session
│   ├── models.py            # ORM-модели
│   ├── schemas.py           # Pydantic-схемы
│   ├── api/                 # роуты: auth, events, bets, wallet
│   ├── services/            # auth, wallet, betting, settlement, sync
│   ├── providers/           # абстракция спорта: base, parser, football, dota
│   └── workers/             # APScheduler: импорт + расчёт
├── alembic/                 # миграции
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Быстрый старт (тестовый режим: SQLite + mock-данные)

По умолчанию `.env` настроен на SQLite и mock-провайдер — ничего ставить не нужно,
кроме зависимостей Python.

```powershell
pip install -r requirements.txt
python -m scripts.seed_mock        # создаёт БД, таблицы, 14 тестовых событий, demo-пользователя
uvicorn app.main:app --reload --port 8000
```

Откройте в браузере: **http://localhost:8000** — готовый интерфейс (вход: `demo@example.com` / `demo123`).
Документация API: http://localhost:8000/docs

Фронтенд (ванильный JS/CSS) раздаётся самим FastAPI из `app/static/` — отдельный сервер не нужен.

### Интерфейс

- **Вход / Регистрация** — стартовый баланс 10 000 VC при регистрации
- **События** — карточки матчей (футбол / Dota 2) с коэффициентами; клик по коэффициенту открывает купон ставки
- **Купон ставки** — сумма, быстрые суммы (100/500/1000/Всё), живой расчёт возможного выигрыша
- **Мои ставки** — таблица со статусами (Ожидает / Выигрыш / Проигрыш / Возврат) и выплатами
- **Кошелёк** — баланс + история транзакций
- Навбар показывает текущий баланс, обновляется после ставок и выплат

### Полный цикл за минуту (через /docs или curl)

1. `POST /api/auth/login` `{ "email": "demo@example.com", "password": "demo123" }` → `access_token`
2. `GET /api/events` (с заголовком `Authorization: Bearer <token>`) → список матчей с коэффициентами
3. `POST /api/bets` `{ "selection_id": <id>, "amount": 500 }` → ставка, баланс списан
4. `GET /api/wallet/balance` → текущий остаток

### Ручной расчёт события (для быстрого теста выплаты)

Не ждать окончания матча — рассчитать сразу:

```powershell
python -m scripts.settle_event <event_id> home   # или away / draw / void
```

После этого выигрышные ставки получают выплату, баланс обновляется.
Проверить: `GET /api/bets` (status = won/lost) и `GET /api/wallet/transactions`.

### Smoke-тест логики (без HTTP)

```powershell
python -m scripts.smoke_test      # регистрация -> ставка -> расчёт -> проверка выплаты
```

## Продакшн-режим (PostgreSQL + реальные провайдеры)

1. Установить и запустить PostgreSQL, создать БД:

```powershell
psql -U postgres -c "CREATE DATABASE betting_virtual;"
```

2. В `.env` раскомментировать PostgreSQL-URL и закомментировать SQLite-URL,
   выставить `FOOTBALL_PROVIDER=parser`, `DOTA_PROVIDER=parser`.

3. Применить миграции и запустить:

```powershell
alembic upgrade head
uvicorn app.main:app --port 8000
```

## Основные эндпоинты

| Метод | Путь                  | Описание                          | Auth |
|-------|-----------------------|-----------------------------------|------|
| POST  | /api/auth/register    | Регистрация, выдаёт стартовый баланс | нет |
| POST  | /api/auth/login       | Вход, возвращает JWT              | нет  |
| GET   | /api/auth/me          | Текущий пользователь              | да   |
| GET   | /api/events           | Список предстоящих событий        | да   |
| GET   | /api/events/{id}      | Событие с маркетами и исходами    | да   |
| POST  | /api/bets             | Сделать ставку                    | да   |
| GET   | /api/bets             | История ставок                    | да   |
| GET   | /api/wallet/balance   | Баланс виртуальной валюты         | да   |
| GET   | /api/wallet/transactions | История транзакций             | да   |

## Поток данных

1. **Планировщик** раз в `SCHEDULER_FETCH_INTERVAL_MINUTES` опрашивает провайдеров
   и upsert-ит события + коэффициенты в БД.
2. Пользователь ставит на `selection` — списывается виртуальный баланс, создаётся `Bet`
   со снимком коэффициента.
3. После матча (с задержкой `SETTLE_GRACE_MINUTES`, чтобы не опрашивать live) планировщик
   опрашивает результаты; при статусе `finished` вызывается `settle_event`, который
   рассчитывает все pending-ставки (выигрыш → зачисление, проигрыш → 0, возврат при void).

## Реальные данные: The Odds API

По умолчанию `FOOTBALL_PROVIDER=odds_api` / `DOTA_PROVIDER=odds_api` — реальные
коэффициенты агрегируются из букмекеров через [The Odds API](https://the-odds-api.com).

### Настройка

1. Зарегистрируйтесь на https://the-odds-api.com и получите бесплатный API-ключ (500 запросов/мес).
2. Впишите его в `.env`:
   ```
   ODDS_API_KEY=ваш_ключ_здесь
   ```
3. Посмотрите доступные виды спорта (бесплатно, без расхода квоты):
   ```powershell
   python -m scripts.list_odds_sports
   ```
4. Впишите нужные спорт-ключи в `.env`:
   - `ODDS_API_FOOTBALL_SPORTS` — например `soccer_epl,soccer_uefa_champs_league`
   - `ODDS_API_DOTA_SPORTS` — киберспорт ищите в выводе `list_odds_sports`
     (`lol`, `cs_go` и т.п.; Dota 2 может быть недоступна — тогда оставьте пустым)
5. Удалите старую БД и пересидируйте:
   ```powershell
   del betting.db
   python -m scripts.seed_mock
   uvicorn app.main:app --reload --port 8000
   ```

Коэффициенты по каждому исходу **усредняются по всем букмекерам** в регионе `ODDS_API_REGIONS`.

### Квота (бесплатный тариф 500/мес)

Расход: 1 кредит за регион×рынок на запрос `/odds`, 2 кредита на `/scores?daysFrom=3`.
Дефолтные интервалы рассчитаны на комфортное использование:
- импорт 2 лиг каждые 4 ч ≈ 360/мес
- расчёт только завершившихся матчей (с grace 120 мин) ≈ 40/мес

В логах видно остаток квоты (`x-requests-remaining`). При превышении — HTTP 429,
провайдер временно возвращает пустой список без падения.

### Если нужен тестовый режим без ключа

В `.env`:
```
FOOTBALL_PROVIDER=mock
DOTA_PROVIDER=mock
```
Будут сгенерированы тестовые события (см. `scripts/seed_mock`).

## Парсинг реальных БК (альтернатива)

Парсеры в `app/providers/football.py` и `dota.py` — каркасы под конкретный сайт БК.
Хрупко (вёрстка меняется) и может нарушать ToS сайта. Рекомендуется The Odds API.

## Дальнейшие шаги

- Киберспорт: подключить OpenDota/PandaScore для расписания Dota 2 (если The Odds API не покрывает)
- Экспресс-ставки (live), тоталы, форы, точный счёт
- Лидерборд по доходности, достижения
- Ограничение максимальной ставки, анти-манипуляции коэффициентами
- WebSocket для обновления коэффициентов в реальном времени
