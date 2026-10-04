"""Deploy zip berisi index.html ke Netlify via REST API."""
import io
import zipfile
import aiohttp

NETLIFY_API = "https://api.netlify.com/api/v1"


async def deploy_netlify(token: str, site_name: str, html_content: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as sess:
        # 1. create site
        async with sess.post(
            f"{NETLIFY_API}/sites",
            headers=headers,
            json={"name": site_name},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            site = await resp.json()
            if resp.status >= 400:
                raise RuntimeError(f"Netlify create site failed: {site}")
            site_id = site["id"]

        # 2. zip in-memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("index.html", html_content)
        buf.seek(0)

        # 3. deploy
        async with sess.post(
            f"{NETLIFY_API}/sites/{site_id}/deploys",
            headers={**headers, "Content-Type": "application/zip"},
            data=buf.read(),
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            deploy = await resp.json()
            if resp.status >= 400:
                raise RuntimeError(f"Netlify deploy failed: {deploy}")
            return deploy.get("ssl_url") or deploy.get("url")
