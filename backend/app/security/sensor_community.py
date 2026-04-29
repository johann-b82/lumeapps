"""Fernet encryption helpers for SNMP community strings.

Thin wrapper over the existing backend/app/security/fernet.py helpers
(which already use the FERNET_KEY env var for Personio credentials).
Exists purely for call-site readability — sensor code reads as
encrypt_community(plaintext) not encrypt_credential(plaintext).

Per PITFALLS.md C-3: community strings are secrets (read access to
environmental data + interface stats on the SNMP agent). Never log,
never echo, never persist plaintext.
"""
from app.security.fernet import decrypt_credential, encrypt_credential


def encrypt_community(plaintext: str) -> bytes:
    """Encrypt a plaintext community string. Returns Fernet token bytes."""
    return encrypt_credential(plaintext)


def decrypt_community(ciphertext: bytes) -> str:
    """Decrypt a Fernet community token. Raises ValueError on tampered token."""
    return decrypt_credential(ciphertext)
