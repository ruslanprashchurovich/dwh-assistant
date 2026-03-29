# DWH ASSISTANT

**DWH ASSISTANT** — это интеллектуальный сервис, который позволяет пользователям формулировать запросы к базе данных **естественным языком**. Сервис автоматически преобразует такие запросы в корректный SQL-код с помощью **YandexGPT**, выполняет его и возвращает результат.

![alt text](image.png)

Это решение упрощает работу аналитиков, менеджеров и других специалистов, которым нужны данные, но нет опыта в написании SQL.

## Как запустить проект

### 1. Настройка окружения

Создайте файл `.env` в корневой папке проекта (`assistant/`) со следующими переменными:

```env
DEBUG_MODE=0
LLM_PROVIDER=YANDEX
PG_STUDENT_HOST=<your db host>
PG_STUDENT_USER=<your db user>
PG_STUDENT_DBNAME=<your db name>
PG_STUDENT_PASSWORD=<your db password>
PG_STUDENT_PORT=<your db port>
YANDEX_CLOUD_API_KEY=<your yandex api-key>
YANDEX_CLOUD_FOLDER=<your yandex folder id>
YANDEX_CLOUD_MODEL=<yandex cloud model name>
TABLES=<tables for analysis>
```

> Замените значения в угловых скобках на реальные данные вашей ClickHouse-базы и Yandex Cloud.

### 2. Установка и запуск

Выполните следующие команды в терминале **последовательно**:

```bash
make setup
.venv\Scripts\activate
make run
```

> На Linux вместо `.venv\Scripts\activate` используйте:
>
> ```cmd
> source .venv/bin/activate
> ```

После этого сервис будет доступен локально (обычно по адресу `http://127.0.0.1:8000`).

## Технологии

- **Языковая модель**: YandexGPT (через Yandex Cloud)
- **База данных**: ClickHouse
- **Backend**: Python (Flask)
- **Управление зависимостями**: `make`, виртуальное окружение
