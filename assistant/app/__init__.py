import os
from dotenv import load_dotenv

# Сначала пытаемся загрузить .env из текущей рабочей директории и выше (например, из корня проекта)
load_dotenv()

# Для обратной совместимости загружаем .env из папки приложения, если он существует
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

from .app import assistant_app as app


def create_app():
    return app
