from urllib.parse import quote

import httpx

from app.core.settings import settings


class StorageClient:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": "application/json",
        }

    async def create_signed_upload_url(self, object_path: str) -> str:
        encoded_path = quote(object_path, safe="/")
        url = f"{settings.supabase_url}/storage/v1/object/upload/sign/{settings.supabase_storage_bucket}/{encoded_path}"
        payload = {"expiresIn": settings.signed_upload_ttl_seconds}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()
        if "signedURL" in data:
            return f"{settings.supabase_url}{data['signedURL']}"
        if "url" in data:
            return f"{settings.supabase_url}{data['url']}"
        raise ValueError("Supabase signed upload response missing URL field")

    async def object_exists(self, object_path: str) -> bool:
        encoded_path = quote(object_path, safe="/")
        url = f"{settings.supabase_url}/storage/v1/object/info/{settings.supabase_storage_bucket}/{encoded_path}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=self._headers)
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True

    async def download_object(self, object_path: str) -> bytes:
        encoded_path = quote(object_path, safe="/")
        url = f"{settings.supabase_url}/storage/v1/object/{settings.supabase_storage_bucket}/{encoded_path}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            return response.content
