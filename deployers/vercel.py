"""Deploy satu file HTML statis ke Vercel via REST API v13."""
import asyncio
import json
import aiohttp

VERCEL_API = "https://api.vercel.com"


async def deploy_vercel(token: str, project_name: str, html_content: str) -> str:
    """Return production URL."""
    token = token.strip()
    if not token:
        raise RuntimeError("VERCEL_TOKEN kosong di config.py")
    if ":" in token:
        raise RuntimeError(
            "VERCEL_TOKEN kayak Bot Telegram token (ada ':'). "
            "Ambil dari https://vercel.com/account/tokens"
        )

    # Pastiin html_content beneran string HTML, bukan JSON/bytes/dict
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8")
    if isinstance(html_content, dict):
        raise RuntimeError("html_content itu dict, bukan string HTML")
    if not isinstance(html_content, str):
        raise RuntimeError(f"html_content tipe salah: {type(html_content)}")
    if not html_content.lstrip().startswith("<"):
        raise RuntimeError(
            f"html_content nggak keliatan HTML. 100 char pertama: "
            f"{html_content[:100]!r}"
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": project_name,
        "files": [{"file": "index.html", "data": html_content}],
        "projectSettings": {
            "framework": None,
            "buildCommand": None,
            "outputDirectory": None,
            "installCommand": None,
            "rootDirectory": None,
        },
        "target": "production",
    }

    async with aiohttp.ClientSession() as sess:
        async with sess.post(
            f"{VERCEL_API}/v13/deployments",
            headers=headers,
            data=json.dumps(payload),
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            body = await resp.json()
            if resp.status == 403 and body.get("error", {}).get("invalidToken"):
                raise RuntimeError(
                    "Vercel nolak token (403 invalidToken). "
                    "Jalanin `python test_token.py` buat verifikasi."
                )
            if resp.status >= 400:
                raise RuntimeError(f"Vercel deploy failed [{resp.status}]: {body}")

            deploy_id = body.get("id")
            url = body.get("url")
            if not url:
                raise RuntimeError(f"Vercel response tanpa url: {body}")

            # poll sampai READY
            for _ in range(30):
                async with sess.get(
                    f"{VERCEL_API}/v13/deployments/{deploy_id}",
                    headers=headers,
                ) as poll:
                    p = await poll.json()
                    state = p.get("readyState") or p.get("status")
                    if state in ("READY", "ready"):
                        final_url = p.get("url", url)
                        # verifikasi konten yang di-serve = HTML
                        await _verify_served_html(final_url)
                        return f"https://{final_url}"
                    if state in ("ERROR", "CANCELED"):
                        raise RuntimeError(f"Vercel build gagal: {p}")
                await asyncio.sleep(3)

            return f"https://{url}"


async def _verify_served_html(host_url: str):
    """Cek URL yang di-serve beneran HTML, bukan JSON/raw."""
    target = host_url if host_url.startswith("http") else f"https://{host_url}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                target,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as r:
                ct = r.headers.get("Content-Type", "")
                snippet = (await r.text())[:200]
                if "text/html" not in ct.lower():
                    raise RuntimeError(
                        f"Vercel serve bukan HTML. Content-Type: {ct}. "
                        f"Snippet: {snippet!r}"
                    )
                if "<html" not in snippet.lower() and "<!doctype" not in snippet.lower():
                    raise RuntimeError(
                        f"Vercel serve bukan HTML. Snippet: {snippet!r}"
                    )
    except aiohttp.ClientError as e:
        # network glitch, jangan gagalin deploy
        print(f"[verify] skip, network error: {e}")
