"""Windows user-scoped DPAPI storage for the private Fugle key.

No plaintext API key is written to disk, printed, or sent to GitHub.
Windows DPAPI protects to the current Windows login; malware running as that
user may still decrypt it. This is NOT a hardware-backed secret vault.
"""
import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import tempfile


class SecretStoreError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi(data: bytes, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise SecretStoreError("僅支援 Windows DPAPI")
    if not data:
        raise SecretStoreError("金鑰資料不可為空")

    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    blob = DATA_BLOB(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    dest = DATA_BLOB()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.restype = wintypes.BOOL
    if decrypt:
        fn.argtypes = [
            ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
            ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
        ]
        args = (ctypes.byref(blob), None, None, None, None, 1, ctypes.byref(dest))
    else:
        fn.argtypes = [
            ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
        ]
        args = (ctypes.byref(blob), "AI Daytrade private local Fugle key",
                None, None, None, 1, ctypes.byref(dest))
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(*args):
        raise SecretStoreError("Windows DPAPI 加解密失敗")
    try:
        return ctypes.string_at(dest.pbData, dest.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(dest.pbData, ctypes.c_void_p))


def default_secret_file() -> Path:
    return Path.home() / ".ai-daytrade-private" / "fugle-key-v108.dpapi"


def save_key(key: str, path=None):
    if not isinstance(key, str) or len(key.strip()) < 12:
        raise SecretStoreError("Fugle API Key 格式不足")
    dest = Path(path or default_secret_file())
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    protected = base64.b64encode(_dpapi(key.strip().encode("utf-8"), False))
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".fugle-v108-", dir=str(dest.parent))
        with os.fdopen(fd, "wb") as stream:
            stream.write(protected)
        os.replace(tmp, dest)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def load_key(path=None) -> str:
    source = Path(path or default_secret_file())
    try:
        protected = base64.b64decode(source.read_bytes(), validate=True)
        key = _dpapi(protected, True).decode("utf-8")
        if len(key) < 12:
            raise SecretStoreError("保護的 API Key 不合法")
        return key
    except (ValueError, UnicodeDecodeError, OSError) as exc:
        raise SecretStoreError("無法讀取此 Windows 帳戶的私人 Fugle Key") from exc
