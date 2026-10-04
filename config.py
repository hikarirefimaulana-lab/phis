"""Config terpusat — semua credential di sini. Jangan commit ke public repo."""
from pathlib import Path

# ───── Telegram Bot ─────
BOT_TOKEN = "ISI_TOKEN_BOT_LU_DI_SINI"
ADMIN_CHAT_ID = 5908693941

# ───── Deployer Credentials ─────
VERCEL_TOKEN = ""
NETLIFY_TOKEN = ""

# ───── Runtime ─────
DB_PATH = "deployer.db"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "cf_challenge.html"

# ───── Limits ─────
MAX_DEPLOY_PER_USER_PER_DAY = 10
MAX_PROJECT_NAME_LEN = 32
