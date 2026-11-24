"""Generate VAPID keypair LOCALLY, outside GitHub and public directories."""
from pathlib import Path
import base64
import os
import sys
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat


def generate(path=None):
    dest = Path(path or (Path.home() / ".ai-daytrade-private" / "vapid-private.pem"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError("私鑰已存在，不覆蓋以免舊手機訂閱失效")
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    with open(dest, "xb") as f:
        f.write(pem)
    try:
        os.chmod(dest, 0o600)
    except OSError:
        pass
    public = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return str(dest), base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii")


if __name__ == "__main__":
    private_path, public = generate(sys.argv[1] if len(sys.argv) > 1 else None)
    print("私鑰已儲存在本機（勿上傳）：", private_path)
    print("VAPID_PUBLIC_KEY（可公開，貼入私人伺服器環境變數）：", public)
