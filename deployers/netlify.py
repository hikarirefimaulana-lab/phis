"""Deploy zip berisi index.html ke Netlify via REST API."""
import io
import zipfile
import aiohttp

NETLIFY_API = "https://api.netlify.com/api/v1"


async def deploy_netlify(token: str, site_name: str, html_content: str) -> str:
    """Return production URL."""
    token = token.strip()
    if not token:
        raise RuntimeError("NETLIFY_TOKEN kosong di config.py")

    headers = {"Authorization": f"Bearer {token}"}

    # Pastiin html_content itu string beneran
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8")

    async with aiohttp.ClientSession() as sess:
        # 1. create site (kalau 409/422 = nama udah dipakai, coba unique suffix)
        site_id = None
        site_url = None

        async with sess.post(
            f"{NETLIFY_API}/sites",
            headers=headers,
            json={"name": site_name},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.json()
            if resp.status in (200, 201):
                site_id = body["id"]
                site_url = body.get("ssl_url") or body.get("url")
            elif resp.status in (409, 422):
                # nama bentrok — tambah suffix random
                import secrets
                new_name = f"{site_name}-{secrets.token_hex(3)}"
                async with sess.post(
                    f"{NETLIFY_API}/sites",
                    headers=headers,
                    json={"name": new_name},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r2:
                    b2 = await r2.json()
                    if r2.status not in (200, 201):
                        raise RuntimeError(f"Netlify create site gagal: {b2}")
                    site_id = b2["id"]
                    site_url = b2.get("ssl_url") or b2.get("url")
            else:
                raise RuntimeError(f"Netlify create site failed [{resp.status}]: {body}")

        # 2. bikin zip dengan STRUKTUR KETAT: index.html di root, no folder
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            # compress_type=ZIP_DEFLATED + arcname eksplisit "index.html"
            z.writestr(
                zipfile.ZipInfo("index.html"),
                html_content.encode("utf-8"),
                compress_type=zipfile.ZIP_DEFLATED,
            )
        buf.seek(0)
        zip_bytes = buf.read()

        # sanity check — pastiin zip valid
        verify = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = verify.namelist()
        if names != ["index.html"]:
            raise RuntimeError(f"Zip isi nggak bener: {names}")
        verify.close()

        # 3. deploy — WAJIB Content-Type: application/zip
        async with sess.post(
            f"{NETLIFY_API}/sites/{site_id}/deploys",
            headers={
                **headers,
                "Content-Type": "application/zip",
            },
            data=zip_bytes,
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            deploy = await resp.json()
            if resp.status >= 400:
                raise RuntimeError(f"Netlify deploy failed [{resp.status}]: {deploy}")

            # balikin URL yang bener — ssl_url paling reliable
            final_url = deploy.get("ssl_url") or deploy.get("url") or site_url
            if not final_url:
                raise RuntimeError(f"Netlify response tanpa url: {deploy}")
            return final_url
