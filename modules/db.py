"""
Capa de persistencia del DSS (SQLite · estándar library).

Tablas:
    usuarios           -> credenciales y perfiles (hash PBKDF2-SHA256)
    recuperaciones     -> códigos de recuperación de contraseña (flujo seguro)
    ordenes_compra     -> órdenes de reposición generadas por el motor EOQ/ROP

Este módulo es la base sobre la que se integrará el backend REST (FastAPI/ASGI).
"""

import os
import sqlite3
import hashlib
import hmac
import base64
import json
import time
import secrets

DB_PATH = "data/dss.db"

PBKDF2_ITERACIONES = 600000


# ---------------------------------------------------------------------------
# Hashing de contraseñas (PBKDF2-HMAC-SHA256 · estándar library)
# ---------------------------------------------------------------------------

def _hash_b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("utf-8").rstrip("=")


def hash_password(password: str) -> str:
    """Genera hash PBKDF2-SHA256 del tipo: pbkdf2_sha256$<iter>$<salt>$<hash>."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERACIONES, dklen=32
    )
    return f"pbkdf2_sha256${PBKDF2_ITERACIONES}${_hash_b64(salt)}${_hash_b64(digest)}"


def verificar_password(password: str, hash_str: str) -> bool:
    """Verifica un password contra un hash PBKDF2-SHA256 (formato dinámico)."""
    if not hash_str:
        return False
    try:
        metodo, iter_str, salt_b64, hash_b64 = str(hash_str).split("$")
        if metodo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
        expected = base64.b64decode(hash_b64 + "=" * (-len(hash_b64) % 4))
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iter_str),
            dklen=32,
        )
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        # Compatibilidad con registros legados en texto plano (solo demo)
        return hmac.compare_digest(str(hash_str), str(password))


# ---------------------------------------------------------------------------
# Conexión SQLite
# ---------------------------------------------------------------------------

def _conectar():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_db() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                rol TEXT NOT NULL,
                nombre TEXT NOT NULL,
                activo INTEGER DEFAULT 1,
                creado_en TEXT NOT NULL,
                ultimo_acceso TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recuperaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                correo TEXT NOT NULL,
                codigo TEXT NOT NULL,
                expira_en REAL NOT NULL,
                intentos INTEGER DEFAULT 0,
                usado INTEGER DEFAULT 0,
                creado_en REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ordenes_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calibre TEXT NOT NULL,
                eoq_kg REAL NOT NULL,
                inversion_usd REAL NOT NULL,
                accion TEXT NOT NULL,
                estatus TEXT NOT NULL,
                usuario TEXT,
                creado_en TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expira_en REAL NOT NULL,
                revocado_en REAL,
                creado_en REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT,
                correo TEXT,
                evento TEXT NOT NULL,
                detalle TEXT,
                exito INTEGER NOT NULL DEFAULT 0,
                creado_en REAL NOT NULL
            )
            """
        )
        conn.commit()

        # Garantizar usuarios base (Gerencia, Operaciones y Administrador de Sistema)
        semilla = [
            ("admin", "josephorrorque17@gmail.com", "admin123", "Administrador", "Soporte del Sistema (IT)"),
            ("gerente", "dinversionesd0204@gmail.com", "admin123", "Gerencia", "Director Logístico"),
            ("operador", "fernandouah23@gmail.com", "planta123", "Operaciones", "Supervisor de Almacén"),
        ]
        for uid, mail, pwd, rol, nom in semilla:
            existe_u = conn.execute("SELECT email FROM usuarios WHERE id = ?", (uid,)).fetchone()
            if not existe_u:
                conn.execute(
                    "INSERT INTO usuarios (id, email, password_hash, rol, nombre, creado_en) VALUES (?, ?, ?, ?, ?, ?)",
                    (uid, mail, hash_password(pwd), rol, nom, time.strftime("%Y-%m-%d %H:%M:%S")),
                )
            elif str(existe_u["email"]).endswith("@d-02-04.com"):
                conn.execute(
                    "UPDATE usuarios SET email = ? WHERE id = ?",
                    (mail, uid),
                )
        conn.commit()


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def crear_usuario(user_id: str, email: str, password: str, rol: str, nombre: str) -> None:
    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO usuarios (id, email, password_hash, rol, nombre, creado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email=excluded.email,
                password_hash=excluded.password_hash,
                rol=excluded.rol,
                nombre=excluded.nombre,
                activo=1
            """,
            (user_id, email, hash_password(password), rol, nombre, time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()


def obtener_usuario(user_id_o_email: str) -> dict | None:
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT * FROM usuarios WHERE id = ? OR email = ?",
            (user_id_o_email, user_id_o_email),
        ).fetchone()
    if fila is None:
        return None
    return dict(fila)


def todos_los_usuarios() -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute("SELECT * FROM usuarios ORDER BY creado_en").fetchall()
    return [dict(f) for f in filas]


def actualizar_password(user_id: str, password: str) -> None:
    with _conectar() as conn:
        conn.execute(
            "UPDATE usuarios SET password_hash = ?, activo = 1 WHERE id = ?",
            (hash_password(password), user_id),
        )
        conn.commit()


def cambiar_estado_usuario(user_id: str, activo: bool) -> None:
    with _conectar() as conn:
        conn.execute(
            "UPDATE usuarios SET activo = ? WHERE id = ?",
            (1 if activo else 0, user_id),
        )
        conn.commit()


def eliminar_usuario(user_id: str) -> None:
    if user_id == "admin":
        return
    with _conectar() as conn:
        conn.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        conn.commit()


def registrar_recuperacion(usuario: str, correo: str, codigo: str) -> None:
    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO recuperaciones (usuario, correo, codigo, expira_en, intentos, creado_en)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (usuario, correo, codigo, time.time() + 300, time.time()),
        )
        conn.commit()


def validar_recuperacion(usuario: str, codigo: str) -> dict | None:
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT * FROM recuperaciones WHERE usuario = ? AND usado = 0 ORDER BY id DESC LIMIT 1",
            (usuario,),
        ).fetchone()
    if fila is None:
        return None
    if time.time() > fila["expira_en"]:
        return None
    if fila["codigo"] != codigo:
        conn = _conectar()
        with conn:
            conn.execute(
                "UPDATE recuperaciones SET intentos = intentos + 1 WHERE id = ?",
                (fila["id"],),
            )
        return None
    return dict(fila)


def marcar_recuperacion_usada(usuario: str) -> None:
    with _conectar() as conn:
        conn.execute("UPDATE recuperaciones SET usado = 1 WHERE usuario = ?", (usuario,))
        conn.commit()


# ---------------------------------------------------------------------------
# Órdenes de compra
# ---------------------------------------------------------------------------

def registrar_orden(
    calibre: str,
    eoq_kg: float,
    inversion_usd: float,
    accion: str,
    estatus: str,
    usuario: str = None,
) -> int:
    with _conectar() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ordenes_compra (calibre, eoq_kg, inversion_usd, accion, estatus, usuario, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (calibre, float(eoq_kg), float(inversion_usd), accion, estatus, usuario, time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return int(cursor.lastrowid)


def listar_ordenes(limite: int = 100) -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT * FROM ordenes_compra ORDER BY id DESC LIMIT ?",
            (int(limite),),
        ).fetchall()
    return [dict(f) for f in filas]


def contar_ordenes() -> int:
    with _conectar() as conn:
        fila = conn.execute("SELECT COUNT(*) AS c FROM ordenes_compra").fetchone()
    return int(fila["c"] or 0)


def actualizar_estado_orden(orden_id: int, nuevo_estatus: str, nueva_accion: str = None) -> None:
    with _conectar() as conn:
        if nueva_accion:
            conn.execute(
                "UPDATE ordenes_compra SET estatus = ?, accion = ? WHERE id = ?",
                (nuevo_estatus, nueva_accion, int(orden_id)),
            )
        else:
            conn.execute(
                "UPDATE ordenes_compra SET estatus = ? WHERE id = ?",
                (nuevo_estatus, int(orden_id)),
            )
        conn.commit()


def eliminar_orden(orden_id: int) -> None:
    with _conectar() as conn:
        conn.execute("DELETE FROM ordenes_compra WHERE id = ?", (int(orden_id),))
        conn.commit()


# ---------------------------------------------------------------------------
# Refresh tokens (flujo de renovación de sesión JWT)
# ---------------------------------------------------------------------------

def crear_refresh_token(usuario_id: str) -> str:
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO refresh_tokens (usuario_id, token_hash, expira_en, creado_en)
            VALUES (?, ?, ?, ?)
            """,
            (usuario_id, token_hash, time.time() + 604800, time.time()),
        )
        conn.commit()
    return token


def validar_refresh_token(token: str, usuario_id: str = None):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash = ? AND revocado_en IS NULL",
            (token_hash,),
        ).fetchone()
    if fila is None:
        return None
    if time.time() > fila["expira_en"]:
        return None
    if usuario_id and fila["usuario_id"] != usuario_id:
        return None
    return dict(fila)


def revocar_refresh_token(token: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _conectar() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET revocado_en = ? WHERE token_hash = ?",
            (time.time(), token_hash),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Auditoría de accesos
# ---------------------------------------------------------------------------

def registrar_auditoria(usuario_id, correo, evento: str, detalle: str = "", exito: bool = False) -> None:
    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO auditoria (usuario_id, correo, evento, detalle, exito, creado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (usuario_id, correo, evento, detalle, 1 if exito else 0, time.time()),
        )
        conn.commit()


def listar_auditoria(limite: int = 100) -> list[dict]:
    with _conectar() as conn:
        filas = conn.execute(
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?",
            (int(limite),),
        ).fetchall()
    return [dict(f) for f in filas]
