"""
Backend REST del DSS (ASGI · sin dependencias externas).

Endpoints:
    GET  /api/salud             -> estado del servicio
    POST /api/auth/login        -> autenticación con usuario + password (retorna JWT)
    GET  /api/auth/validar      -> valida token JWT (?token=xxx)
    GET  /api/ordenes           -> listado de órdenes de compra
    POST /api/ordenes           -> registro de nueva orden de compra

Uvicorn: uvicorn run api:api --host 0.0.0.0 --port 8501
"""

import json
import time
from typing import Any

from modules import db as db_persistencia
from modules.security import crear_jwt, validar_jwt

_intentos_login: dict = {}


async def _send_json(send, status_code: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"access-control-allow-origin", b"*"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _leer_cuerpo(receive) -> bytes:
    body = b""
    while True:
        msg = await receive()
        if msg.get("type") == "http.request":
            chunk = msg.get("body", b"")
            body += chunk
            if len(body) >= int(msg.get("content-length") or 0):
                break
        elif msg.get("type") == "http.disconnect":
            break
    return body


def _query_token(scope) -> str:
    for hk, hv in scope.get("headers") or []:
        if hk.lower() == b"authorization":
            val = hv.decode("utf-8", errors="ignore").strip()
            if val.lower().startswith("bearer "):
                return val[7:].strip()
    query = scope.get("query_string") or b""
    params = {}
    for parte in query.decode("utf-8").split("&"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            from urllib.parse import unquote_plus

            params[unquote_plus(k)] = unquote_plus(v)
    return params.get("token") or ""


async def api(scope, receive, send):
    if scope.get("type") != "http":
        return

    method = scope.get("method") or ""
    path = scope.get("path") or ""

    if method == "OPTIONS":
        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [
                    (b"access-control-allow-origin", b"*"),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                    (b"access-control-allow-headers", b"Content-Type, Authorization"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})
        return

    if method == "GET" and path == "/api/salud":
        try:
            db_persistencia.inicializar_db()
            usuarios_activos = len([u for u in db_persistencia.todos_los_usuarios() if u.get("activo")])
            total_ordenes = db_persistencia.contar_ordenes()
            db_ok = True
        except Exception:
            usuarios_activos = 0
            total_ordenes = 0
            db_ok = False
        await _send_json(
            send,
            200,
            {
                "status": "ok",
                "servicio": "DSS Core",
                "base_datos": "ok" if db_ok else "degradado",
                "usuarios_activos": usuarios_activos,
                "ordenes_registradas": total_ordenes,
                "cors": "enabled",
                "rate_limit": "2 int / 5 min (Anti-DDoS)",
            },
        )
        return

    if method == "POST" and path == "/api/auth/login":
        ahora = time.time()
        try:
            cuerpo = json.loads((await _leer_cuerpo(receive)).decode("utf-8") or "{}")
        except Exception:
            cuerpo = {}
        identificador = str(cuerpo.get("identificador") or "").strip()
        clave_rl = identificador.lower() or "anon"
        ventana = [t for t in _intentos_login.setdefault(clave_rl, []) if ahora - t < 300]
        _intentos_login[clave_rl] = ventana
        if len(ventana) >= 2:
            await _send_json(
                send,
                429,
                {"detail": "Protección Anti-DDoS activa: máximo 2 intentos fallidos cada 5 minutos."},
            )
            return
        password = str(cuerpo.get("password") or "")
        usuario = db_persistencia.obtener_usuario(identificador) if identificador else None
        exito = False
        if usuario and db_persistencia.verificar_password(password, usuario["password_hash"]):
            _intentos_login.pop(clave_rl, None)
            exito = True
            token = crear_jwt(
                {
                    "sub": usuario["id"],
                    "rol": usuario["rol"],
                    "nombre": usuario["nombre"],
                }
            )
            refresh_token = db_persistencia.crear_refresh_token(usuario["id"])
            db_persistencia.registrar_auditoria(
                usuario["id"], usuario["email"], "LOGIN", "Autenticación exitosa (API)", True
            )
            await _send_json(
                send,
                200,
                {
                    "token": token,
                    "refresh_token": refresh_token,
                    "usuario": usuario["id"],
                    "rol": usuario["rol"],
                    "nombre": usuario["nombre"],
                },
            )
        else:
            _intentos_login.setdefault(clave_rl, []).append(ahora)
            db_persistencia.registrar_auditoria(
                identificador or "anon", identificador or "anon", "LOGIN", "Intento fallido (API)", False
            )
            await _send_json(send, 401, {"detail": "Credenciales inválidas"})
        return

    if method == "POST" and path == "/api/auth/refresh":
        try:
            cuerpo = json.loads((await _leer_cuerpo(receive)).decode("utf-8") or "{}")
        except Exception:
            cuerpo = {}
        refresh_token = str(cuerpo.get("refresh_token") or "")
        usuario = None
        if refresh_token:
            fila = db_persistencia.validar_refresh_token(refresh_token)
            if fila is not None:
                usuario = db_persistencia.obtener_usuario(fila["usuario_id"])
        if usuario is None:
            await _send_json(send, 401, {"detail": "Refresh token inválido o expirado"})
            return
        db_persistencia.revocar_refresh_token(refresh_token)
        token = crear_jwt(
            {"sub": usuario["id"], "rol": usuario["rol"], "nombre": usuario["nombre"]}
        )
        refresh_token = db_persistencia.crear_refresh_token(usuario["id"])
        await _send_json(
            send,
            200,
            {
                "token": token,
                "refresh_token": refresh_token,
                "rol": usuario["rol"],
                "nombre": usuario["nombre"],
            },
        )
        return

    if method == "GET" and path == "/api/auditoria":
        token = _query_token(scope)
        claims = validar_jwt(token) if token else None
        if not claims:
            await _send_json(send, 401, {"detail": "No autorizado"})
            return
        await _send_json(send, 200, {"registros": db_persistencia.listar_auditoria(200)})
        return

    if method == "GET" and path.startswith("/api/usuarios"):
        token = _query_token(scope)
        claims = validar_jwt(token) if token else None
        if not claims:
            await _send_json(send, 401, {"detail": "No autorizado"})
            return
        usuarios = [
            {
                "id": u["id"],
                "email": u["email"],
                "rol": u["rol"],
                "nombre": u["nombre"],
                "activo": u["activo"],
                "creado_en": u["creado_en"],
            }
            for u in db_persistencia.todos_los_usuarios()
        ]
        await _send_json(send, 200, {"usuarios": usuarios})
        return

    if method == "POST" and path == "/api/usuarios":
        token = _query_token(scope)
        claims = validar_jwt(token) if token else None
        if not claims:
            await _send_json(send, 401, {"detail": "No autorizado"})
            return
        try:
            cuerpo = json.loads((await _leer_cuerpo(receive)).decode("utf-8") or "{}")
        except Exception:
            await _send_json(send, 400, {"detail": "Cuerpo JSON inválido"})
            return
        uid = str(cuerpo.get("id") or "").strip().lower()
        email = str(cuerpo.get("email") or "").strip().lower()
        pwd = str(cuerpo.get("password") or "")
        rol = str(cuerpo.get("rol") or "Operaciones")
        nombre = str(cuerpo.get("nombre") or uid)
        if not uid or not email or not pwd:
            await _send_json(send, 400, {"detail": "Campos id, email y password requeridos"})
            return
        db_persistencia.crear_usuario(uid, email, pwd, rol, nombre)
        await _send_json(send, 201, {"detail": "Usuario registrado", "usuario": uid})
        return

    if method == "PUT" and path.startswith("/api/usuarios/"):
        token = _query_token(scope)
        claims = validar_jwt(token) if token else None
        if not claims:
            await _send_json(send, 401, {"detail": "No autorizado"})
            return
        user_id = path[len("/api/usuarios/"):].removesuffix("/password").strip("/")
        try:
            cuerpo = json.loads((await _leer_cuerpo(receive)).decode("utf-8") or "{}")
        except Exception:
            await _send_json(send, 400, {"detail": "Cuerpo JSON inválido"})
            return
        password = str(cuerpo.get("password") or "")
        if not password:
            await _send_json(send, 400, {"detail": "Password requerido"})
            return
        db_persistencia.actualizar_password(user_id, password)
        await _send_json(send, 200, {"detail": "Contraseña actualizada", "usuario": user_id})
        return

    if method == "GET" and path == "/api/auth/validar":
        token = _query_token(scope)
        claims = validar_jwt(token) if token else None
        if claims:
            await _send_json(
                send,
                200,
                {"valido": True, "usuario": claims.get("sub"), "rol": claims.get("rol")},
            )
        else:
            await _send_json(send, 401, {"valido": False, "detail": "Token inválido o expirado"})
        return

    if method == "GET" and path == "/api/ordenes":
        await _send_json(send, 200, {"ordenes": db_persistencia.listar_ordenes()})
        return

    if method == "POST" and path == "/api/ordenes":
        try:
            cuerpo = json.loads((await _leer_cuerpo(receive)).decode("utf-8") or "{}")
        except Exception:
            await _send_json(send, 400, {"detail": "Cuerpo JSON inválido"})
            return
        orden = db_persistencia.registrar_orden(
            calibre=str(cuerpo.get("calibre") or ""),
            eoq_kg=float(cuerpo.get("eoq_kg") or 0),
            inversion_usd=float(cuerpo.get("inversion_usd") or 0),
            accion=str(cuerpo.get("accion") or "COMPRA PREVENTIVA"),
            estatus=str(cuerpo.get("estatus") or "ESTABLE"),
            usuario=str(cuerpo.get("usuario") or "") or None,
        )
        await _send_json(send, 201, {"id": orden, "detalle": "Orden registrada"})
        return

    await _send_json(send, 404, {"detail": "Endpoint no encontrado"})
