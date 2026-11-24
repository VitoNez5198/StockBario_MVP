import bcrypt


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
