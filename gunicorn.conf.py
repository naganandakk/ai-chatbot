"""Gunicorn settings for the Flask API. Gunicorn loads this file from the repo root automatically.

Command-line flags still override these values. Use `APP_ENV=production` when the server sits
behind an HTTPS-terminating proxy, so it serves plain HTTP. Any other value (the default is
`local`) serves HTTPS with a self-signed certificate in `backend/certs/`, created on first start.
"""

import ipaddress
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)

APP_ENV = os.getenv("APP_ENV", "local")
CHAT_STORE = os.getenv("CHAT_STORE", "duckdb")
CERT_DIR = ROOT / "backend" / "certs"


def ensure_local_certificate(cert_dir):
    """Return (certfile, keyfile), generating a self-signed pair if either file is missing."""
    cert_file = cert_dir / "local-cert.pem"
    key_file = cert_dir / "local-key.pem"
    if cert_file.exists() and key_file.exists():
        return str(cert_file), str(key_file)

    cert_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_file.chmod(0o600)
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Created a self-signed local certificate in {cert_dir}", flush=True)
    return str(cert_file), str(key_file)


bind = os.getenv("GUNICORN_BIND", "127.0.0.1:5000")

# DuckDB takes a write lock on its file, and each worker opens it at import, so only Postgres
# can run more than one worker.
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
if CHAT_STORE == "duckdb" and workers != 1:
    raise SystemExit("CHAT_STORE=duckdb needs GUNICORN_WORKERS=1; DuckDB allows one writer.")

# A streaming reply holds the sync worker until it finishes, so allow for slow model replies.
timeout = 120

if APP_ENV == "local":
    certfile, keyfile = ensure_local_certificate(CERT_DIR)
