import os
from cryptography.fernet import Fernet, InvalidToken

_ENV_VAR = "FERNET_KEY"


def _get_fernet() -> Fernet:
    key = os.environ.get(_ENV_VAR)
    if not key:
        raise RuntimeError(f"Environment variable {_ENV_VAR} is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_credential(plaintext: str) -> bytes:
    """Encrypt a plaintext credential string. Returns Fernet token bytes."""
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_credential(ciphertext: bytes) -> str:
    """Decrypt a Fernet token. Raises ValueError on invalid/tampered token."""
    try:
        return _get_fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Credential decryption failed - token invalid or key mismatch") from exc
