from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from config import settings

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

async def verify_admin_key(key: str = Security(api_key_header)) -> None:
    if key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")