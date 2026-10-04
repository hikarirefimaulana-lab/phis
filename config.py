"""Config terpusat — semua credential di sini. Jangan commit ke public repo."""
from pathlib import Path

# ───── Telegram Bot ─────
BOT_TOKEN = "8939022553:AAGzW3RTpHAc3WhyFvI2iEM4YShjP5veMZY"
ADMIN_CHAT_ID = 8086581937

# ───── Deployer Credentials ─────
VERCEL_TOKEN = "vcp_8puDfvHC58UWheyu2y3ORnOM9V4vhWNTnX5WHvXkyqYFzUIPHF1FEqvs"
NETLIFY_TOKEN = "nfp_CzU6FmuLUs2wDqQST22zUoW1A8hkfrke9c9f"

# ───── Runtime ─────
DB_PATH = "deployer.db"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "cf_challenge.html"

# ───── Limits ─────
MAX_DEPLOY_PER_USER_PER_DAY = 10
MAX_PROJECT_NAME_LEN = 32
