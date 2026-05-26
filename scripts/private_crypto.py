"""Encrypt private gallery images (AES-256-GCM, PBKDF2 key derivation)."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

REPO_ROOT = Path(__file__).resolve().parent.parent
PASSWORD_FILE = REPO_ROOT / "private" / ".gallery-password"

ENC_SALT = b"pratik-private-enc-v1"
PBKDF2_ITERATIONS = 100_000


def load_password() -> str:
    env_password = os.environ.get("PRIVATE_GALLERY_PASSWORD", "").strip()
    if env_password:
        return env_password
    if PASSWORD_FILE.is_file():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip()
    raise ValueError(
        "Private gallery password required: set PRIVATE_GALLERY_PASSWORD "
        f"or create {PASSWORD_FILE.relative_to(REPO_ROOT)}"
    )


def derive_key(password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ENC_SALT,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, password: str) -> bytes:
    key = derive_key(password)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def encrypt_file_bytes(jpeg_bytes: bytes, password: str | None = None) -> bytes:
    pwd = password if password is not None else load_password()
    return encrypt_bytes(jpeg_bytes, pwd)
