import bcrypt


def hash_password(plain: str) -> str:
    """비밀번호 → 저장용 해시. 같은 비밀번호라도 매번 다른 해시가 나온다 (salt)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """로그인 시 입력한 비밀번호가 저장된 해시와 맞는지."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())
