import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val not in (None, "") else default
    except ValueError:
        return default


# --- Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@SMOKTOLK")
DISCUSSION_GROUP_ID = _int("DISCUSSION_GROUP_ID", 0)
ADMIN_CHAT_ID = _int("ADMIN_CHAT_ID", 0)

# --- Gemini AI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

# --- Vertex AI (аутентификация через service account, без API-ключа) ---
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


# --- Хранилище ---
DB_PATH = os.getenv("DB_PATH", "/opt/SMOKI/bot/smoki.db")
IMAGE_DIR = os.getenv("IMAGE_DIR", "/opt/SMOKI/bot/images")

# --- Веб (зарезервировано) ---
WEBHOOK_PORT = _int("WEBHOOK_PORT", 8082)

# --- Публикация и модерация ---
PUBLISH_HOUR = _int("PUBLISH_HOUR", 11)
COMMENTS_INTERVAL_HOURS = _int("COMMENTS_INTERVAL_HOURS", 3)
MAX_REGEN = _int("MAX_REGEN", 3)

# --- Категории тем для ротации ---
CATEGORIES = [
    "news",         # новости рынка
    "curious",      # курьёзы, забавные истории
    "science",      # научные открытия
    "novelty",      # новинки продукции
    "history",      # исторические личности
    "nonnicotine",  # безникотиновые альтернативы
]

# --- Окна генерации/публикации ---
GEN_WINDOW_START = _int("GEN_WINDOW_START", 6)
GEN_WINDOW_END = _int("GEN_WINDOW_END", 7)
PUBLISH_WINDOW_START = _int("PUBLISH_WINDOW_START", 11)
PUBLISH_WINDOW_END = _int("PUBLISH_WINDOW_END", 13)
