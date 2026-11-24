import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import get_settings

SESSION_COOKIE_NAME = "sb_session"


def hash_pin(pin: str) -> str:
    pin_limpio = pin.strip()
    if not (pin_limpio.isdigit() and len(pin_limpio) == 4):
        raise ValueError("El PIN debe tener exactamente 4 digitos")
    hashed = bcrypt.hashpw(pin_limpio.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    if not pin or not pin_hash:
        return False
    return bcrypt.checkpw(pin.strip().encode("utf-8"), pin_hash.encode("utf-8"))


def _get_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.secret_key, salt="stockbarrio-session")


def create_session_token(usuario_id: int, almacen_id: int, rol: str) -> str:
    return _get_serializer().dumps(
        {"uid": usuario_id, "aid": almacen_id, "rol": rol}
    )


def read_session_token(token: str) -> dict | None:
    if not token:
        return None
    settings = get_settings()
    max_age = settings.session_expire_hours * 3600
    try:
        data = _get_serializer().loads(token, max_age=max_age)
        if isinstance(data, dict) and "uid" in data and "aid" in data:
            return data
        return None
    except (BadSignature, SignatureExpired):
        return None
