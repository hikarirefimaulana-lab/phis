"""Deploy satu file HTML statis ke Vercel via REST API v13."""
import asyncio
import json
import aiohttp

VERCEL_API = "https://api.vercel.com"


async def deploy_vercel(token: str, project_name: str, html_content: str) -> str:
    """Return production URL."""
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
            if resp.status >= 400:
                raise RuntimeError(f"Vercel deploy failed [{resp.status}]: {body}")

            deploy_id = body.get("id")
            url = body.get("url")
            if not url:
                raise RuntimeError(f"Vercel response tanpa url: {body}")

            # poll sampai ready (max ~90s)
            for _ in range(30):
                async with sess.get(
                    f"{VERCEL_API}/v13/deployments/{deploy_id}",
                    headers=headers,
                ) as poll:
                    p = await poll.json()
                    state = p.get("readyState") or p.get("status")
                    if state in ("READY", "ready"):
                        return f"https://{p.get('url', url)}"
                    if state in ("ERROR", "CANCELED"):
                        raise RuntimeError(f"Vercel build gagal: {p}")
                await asyncio.sleep(3)

            return f"https://{url}"
