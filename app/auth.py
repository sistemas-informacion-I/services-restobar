import os
import base64
import jwt
from pathlib import Path
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

# Load env
current_dir = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=current_dir.parent / ".env")
spring_env = current_dir.parent.parent.parent / "backend-restobar" / ".env"
load_dotenv(dotenv_path=spring_env)

JWT_SECRET_RAW = os.getenv("JWT_SECRET")
if not JWT_SECRET_RAW:
    JWT_SECRET_RAW = "thatqIsMykeyregtfrdesww233eggtwasoddgkjjhhtdhttebd54ndsiuuhhhshs8877465sbbdd"

# Decode secret key from Base64 (matching Spring's Decoders.BASE64.decode)
try:
    missing_padding = len(JWT_SECRET_RAW) % 4
    if missing_padding:
        padded_secret = JWT_SECRET_RAW + '=' * (4 - missing_padding)
    else:
        padded_secret = JWT_SECRET_RAW
    JWT_SECRET = base64.b64decode(padded_secret)
except Exception:
    JWT_SECRET = JWT_SECRET_RAW.encode("utf-8")

security = HTTPBearer()


class CurrentUser:
    def __init__(self, username: str, uid: int, authorities: list):
        self.username = username
        self.uid = uid
        self.authorities = authorities

    def has_permission(self, required_permission: str) -> bool:
        return required_permission in self.authorities


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256", "HS384", "HS512"])

        username = payload.get("sub")
        uid = payload.get("uid")
        authorities = payload.get("authorities", [])

        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token no contiene información de usuario"
            )

        return CurrentUser(
            username=username,
            uid=uid,
            authorities=authorities
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso ha expirado"
        )
    except jwt.InvalidTokenError as e:
        print(f"JWT Validation Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido"
        )


def require_permission(required_permission: str):
    def dependency(user: CurrentUser = Depends(get_current_user)):
        if not user.has_permission(required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: se requiere {required_permission}"
            )
        return user
    return dependency
