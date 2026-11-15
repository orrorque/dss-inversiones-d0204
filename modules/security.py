"""
Seguridad del DSS: firma JWT (HS256) con librería estándar.

Formato: <header>.<payload>.<firma>
  - Header:  {"alg": "HS256", "typ": "JWT"}
  - Payload: {"sub", "rol", "nombre", "iat", "exp"}
  - Firma:   HMAC-SHA256 con secret compartido
"""

import base64
import hashlib
import hmac
import json
import time

JWT_SECRET = "dss_inversiones_d02-04_core_secret"
JWT_EXPIRACION_SEGUNOS = 28800


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("utf-8")


def crear_jwt(payload: dict) -> str:
    encabezado = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    ahora = int(time.time())
    cuerpo = {
        "sub": payload.get("sub") or payload.get("usuario") or "",
        "rol": payload.get("rol") or "Operaciones",
        "nombre": payload.get("nombre") or "Usuario",
        "iat": ahora,
        "exp": ahora + JWT_EXPIRACION_SEGUNOS,
    }
    payload_b64 = _b64url(json.dumps(cuerpo, separators=(",", ":")).encode("utf-8"))
    firma = hmac.new(
        JWT_SECRET.encode("utf-8"),
        f"{encabezado}.{payload_b64}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{encabezado}.{payload_b64}.{_b64url(firma)}"


def validar_jwt(token: str):
    try:
        encabezado, payload_b64, firma = str(token).split(".")
        firma_esperada = _b64url(
            hmac.new(
                JWT_SECRET.encode("utf-8"),
                f"{encabezado}.{payload_b64}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(firma_esperada, firma):
            return None
        cuerpo = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
        if int(cuerpo.get("exp") or 0) < time.time():
            return None
        return cuerpo
    except Exception:
        return None
