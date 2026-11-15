import copy
import logging
import re
import secrets
import time

import streamlit as st

from . import db as db_persistencia
from .notifications import email_alerta_configurado, enviar_codigo_recuperacion
from .security import crear_jwt, validar_jwt
from .theme import chip, obtener_imagen_b64

_log = logging.getLogger("dss.auth")

# Cuentas demo de respaldo (hash PBKDF2 generado en tiempo de ejecución).
USUARIOS_MOCK = {
    "admin": {
        "password": db_persistencia.hash_password("admin123"),
        "rol": "Administrador",
        "nombre": "Soporte del Sistema (IT)",
        "correo": "josephorrorque17@gmail.com",
    },
    "gerente": {
        "password": db_persistencia.hash_password("admin123"),
        "rol": "Gerencia",
        "nombre": "Director Logístico",
        "correo": "dinversionesd0204@gmail.com",
    },
    "operador": {
        "password": db_persistencia.hash_password("planta123"),
        "rol": "Operaciones",
        "nombre": "Supervisor de Almacén",
        "correo": "fernandouah23@gmail.com",
    },
}

MAX_INTENTOS = 2
BLOQUEO_SEGUNDOS = 300
VIGENCIA_CODIGO_SEGUNDOS = 300
LONGITUD_CODIGO = 6
MIN_LONGITUD_PASSWORD = 8


def inicializar_sesion():
    valores = {
        "autenticado": False,
        "rol": None,
        "nombre": None,
        "usuario": None,
        "auth_vista": "login",
        "auth_intentos": 0,
        "auth_bloqueo": 0.0,
        "auth_rec_intentos": 0,
        "auth_rec_bloqueo": 0.0,
        "auth_recuperacion": None,
        "auth_mensaje": None,
    }
    for clave, valor in valores.items():
        st.session_state.setdefault(clave, valor)


# ---------------------------------------------------------------------------
# Utilidades de autenticación
# ---------------------------------------------------------------------------


def _db_usuarios():
    usuarios = {}
    try:
        db_persistencia.inicializar_db()
        for u in db_persistencia.todos_los_usuarios():
            if not u.get("activo"):
                continue
            usuarios[u["id"]] = {
                "password": u["password_hash"],
                "rol": u["rol"],
                "nombre": u["nombre"],
                "correo": u["email"],
            }
    except Exception:
        usuarios = {}
    if not usuarios:
        usuarios = copy.deepcopy(USUARIOS_MOCK)
    st.session_state["usuarios_db"] = usuarios
    return st.session_state["usuarios_db"]


def _buscar_usuario(identificador: str):
    """Permite autenticar o recuperar clave por ID de usuario o correo corporativo."""
    limpio = (identificador or "").strip().lower()
    if not limpio:
        return None, None

    alias_corporativos = {
        "gerencia@d-02-04.com": "gerente",
        "compras@d-02-04.com": "gerente",
        "dinversionesd0204@gmail.com": "gerente",
        "operaciones@d-02-04.com": "operador",
        "admin@d-02-04.com": "admin",
    }
    if limpio in alias_corporativos:
        limpio = alias_corporativos[limpio]

    db = _db_usuarios()
    if limpio in db:
        return limpio, db[limpio]

    for user_id, datos in db.items():
        if datos.get("correo", "").lower() == limpio:
            return user_id, datos

    return None, None


def _enmascarar_correo(correo: str) -> str:
    if "@" not in correo:
        return correo
    local, dominio = correo.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'•' * max(len(local) - len(visible), 3)}@{dominio}"


def _politica_password(password: str):
    if len(password) < MIN_LONGITUD_PASSWORD:
        return f"La contraseña debe tener al menos {MIN_LONGITUD_PASSWORD} caracteres."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "La contraseña debe combinar letras y números."
    return None


def _segundos_bloqueo() -> int:
    return max(0, int(st.session_state.get("auth_bloqueo", 0.0) - time.time()))


def _segundos_bloqueo_rec() -> int:
    return max(0, int(st.session_state.get("auth_rec_bloqueo", 0.0) - time.time()))


def _formatear_tiempo(segundos: int) -> str:
    minutos, seg = divmod(max(0, int(segundos)), 60)
    if minutos > 0:
        return f"{minutos} min {seg:02d} s"
    return f"{seg} s"


@st.fragment(run_every=1)
def _render_reloj_bloqueo(clave_estado: str, subtitulo: str):
    """Renderiza un cronómetro digital en vivo (1 seg) durante el bloqueo Anti-DDoS."""
    restante = max(0, int(st.session_state.get(clave_estado, 0.0) - time.time()))
    if restante <= 0:
        st.session_state[clave_estado] = 0.0
        st.rerun()
        return

    minutos, seg = divmod(restante, 60)
    pct = max(2.0, min(100.0, (restante / float(BLOQUEO_SEGUNDOS)) * 100.0))
    st.html(
        f'<div class="dss-lock-card">'
        f'<div class="dss-lock-kicker"><span class="dss-lock-dot"></span> Escudo Anti-DDoS Activo</div>'
        f'<div class="dss-lock-title">Bloqueo temporal de seguridad ({MAX_INTENTOS}/{MAX_INTENTOS} intentos)</div>'
        f'<div class="dss-lock-sub">{subtitulo}</div>'
        f'<div class="dss-lock-clock">'
        f'<div class="dss-lock-unit"><span class="dss-lock-num">{minutos:02d}</span><span class="dss-lock-lbl">Minutos</span></div>'
        f'<span class="dss-lock-sep">:</span>'
        f'<div class="dss-lock-unit"><span class="dss-lock-num">{seg:02d}</span><span class="dss-lock-lbl">Segundos</span></div>'
        f"</div>"
        f'<div class="dss-lock-bar-track"><div class="dss-lock-bar-fill" style="width:{pct:.1f}%;"></div></div>'
        f"</div>"
    )


@st.fragment(run_every=1)
def _render_panel_otp_vivo():
    """Panel gráfico OTP con reloj de vigencia en vivo y matriz visual de 6 dígitos."""
    recuperacion = st.session_state.get("auth_recuperacion")
    if not recuperacion:
        return

    restante_exp = max(0, int(float(recuperacion.get("expira", 0.0)) - time.time()))
    if restante_exp <= 0:
        st.session_state["auth_recuperacion"] = None
        st.rerun()
        return

    min_e, seg_e = divmod(restante_exp, 60)
    correo_mask = _enmascarar_correo(recuperacion["correo"])
    enviado = bool(recuperacion.get("enviado"))
    intentos_usados = int(recuperacion.get("intentos", 0))
    intentos_rest = max(0, MAX_INTENTOS - intentos_usados)
    color_int = "#34D399" if intentos_rest == MAX_INTENTOS else "#FBBF24"

    estado_txt = (
        f"✓ Despachado a {correo_mask}"
        if enviado
        else f"⚠ Contingencia SMTP · {correo_mask}"
    )

    st.html(
        f'<div class="dss-otp-card">'
        f'<div class="dss-otp-badge-row">'
        f'<span class="dss-otp-mail-pill">{estado_txt}</span>'
        f'<span class="dss-otp-timer-pill">⏱ Vigencia: {min_e:02d}:{seg_e:02d}</span>'
        f"</div>"
        f'<div style="font-size:.76rem;color:#CBD5E1;line-height:1.4;">'
        f"Ingrese los <b>6 dígitos numéricos</b> enviados a su correo para verificar su identidad:"
        f"</div>"
        f'<div class="dss-otp-slots">'
        f'<div class="dss-otp-slot">1</div>'
        f'<div class="dss-otp-slot">2</div>'
        f'<div class="dss-otp-slot">3</div>'
        f'<span class="dss-otp-slot-sep">—</span>'
        f'<div class="dss-otp-slot">4</div>'
        f'<div class="dss-otp-slot">5</div>'
        f'<div class="dss-otp-slot">6</div>'
        f"</div>"
        f'<div class="dss-otp-meta">'
        f'<span>Canal cifrado <b>TLS · SMTP</b></span>'
        f'<span>Intentos disponibles: <b style="color:{color_int};">{intentos_rest} de {MAX_INTENTOS}</b></span>'
        f"</div>"
        f"</div>"
    )


def _cabecera(eyebrow: str, titulo: str, subtitulo: str, paso: str = ""):
    paso_html = f'<div class="dss-auth-step">{paso}</div>' if paso else ""
    st.html(
        '<div class="dss-auth-head">'
        f"{paso_html}"
        f'<div class="dss-auth-eyebrow">{eyebrow}</div>'
        f'<div class="dss-auth-title">{titulo}</div>'
        f'<div class="dss-auth-sub">{subtitulo}</div>'
        "</div>"
    )


def _ir(vista: str):
    st.session_state["auth_vista"] = vista
    st.rerun()


def _generar_codigo(identificador: str) -> tuple[bool, int]:
    """
    Genera y envía el código de recuperación validando el límite Anti-DDoS:
    máximo 2 intentos por usuario cada 5 minutos (300 segundos).
    Retorna (exito, segundos_bloqueo_restantes).
    """
    bloqueo_ses = _segundos_bloqueo_rec()
    if bloqueo_ses > 0:
        return False, bloqueo_ses

    user_id, registro = _buscar_usuario(identificador)
    if registro is None:
        st.session_state["auth_rec_intentos"] = st.session_state.get("auth_rec_intentos", 0) + 1
        try:
            db_persistencia.inicializar_db()
            db_persistencia.registrar_auditoria(
                identificador.strip(),
                identificador.strip(),
                "RECUPERACION_FALLIDA",
                "Intento de recordar usuario inexistente",
                False,
            )
        except Exception:
            pass
        if st.session_state["auth_rec_intentos"] >= MAX_INTENTOS:
            st.session_state["auth_rec_intentos"] = 0
            st.session_state["auth_rec_bloqueo"] = time.time() + BLOQUEO_SEGUNDOS
            return False, BLOQUEO_SEGUNDOS
        return False, 0

    try:
        db_persistencia.inicializar_db()
        seg_db = db_persistencia.segundos_bloqueo_recuperacion(
            user_id, max_intentos=MAX_INTENTOS, ventana_seg=BLOQUEO_SEGUNDOS
        )
    except Exception:
        seg_db = 0

    if seg_db > 0:
        st.session_state["auth_rec_bloqueo"] = time.time() + seg_db
        try:
            db_persistencia.registrar_auditoria(
                user_id,
                registro.get("correo", ""),
                "BLOQUEO_DDOS_RECUPERACION",
                f"Bloqueado por superar {MAX_INTENTOS} solicitudes en 5 min",
                False,
            )
        except Exception:
            pass
        return False, seg_db

    correo_destino = str(registro.get("correo") or "dinversionesd0204@gmail.com").strip()
    if correo_destino.lower().endswith("@d-02-04.com"):
        correo_destino = "dinversionesd0204@gmail.com"

    codigo = "".join(secrets.choice("0123456789") for _ in range(LONGITUD_CODIGO))
    st.session_state["auth_recuperacion"] = {
        "usuario": user_id,
        "correo": correo_destino,
        "codigo": codigo,
        "expira": time.time() + VIGENCIA_CODIGO_SEGUNDOS,
        "intentos": 0,
        "enviado": False,
    }
    try:
        db_persistencia.inicializar_db()
        db_persistencia.registrar_recuperacion(user_id, correo_destino, codigo)
        db_persistencia.registrar_auditoria(
            user_id,
            correo_destino,
            "RECUPERACION_CODIGO",
            "Solicitud de código de recuperación (límite 2/5min)",
            True,
        )
    except Exception:
        pass
    _log.warning(
        "Código de recuperación para '%s' (%s): %s (vigencia %s s)",
        user_id,
        correo_destino,
        codigo,
        VIGENCIA_CODIGO_SEGUNDOS,
    )
    try:
        st.session_state["auth_recuperacion"]["enviado"] = enviar_codigo_recuperacion(
            user_id, correo_destino, codigo
        )
    except Exception:
        st.session_state["auth_recuperacion"]["enviado"] = False
    return True, 0


# ---------------------------------------------------------------------------
# Vistas del flujo de autenticación
# ---------------------------------------------------------------------------


def _vista_login():
    _cabecera(
        "Sistema de Soporte a la Decisión · DSS",
        "Portal de Acceso Corporativo",
        "Gestión de inventario ROP / EOQ y auditoría ABC · Inversiones D-02-04, C.A.",
    )

    mensaje = st.session_state.pop("auth_mensaje", None)
    if mensaje:
        st.success(mensaje)

    bloqueado = _segundos_bloqueo()
    if bloqueado:
        _render_reloj_bloqueo(
            "auth_bloqueo",
            "Se alcanzó el límite de intentos fallidos de inicio de sesión. El acceso se desbloqueará automáticamente al finalizar la cuenta regresiva.",
        )

    with st.form("login_form", border=False):
        identificador = st.text_input(
            "Usuario o correo electrónico",
            placeholder="Ingrese su usuario o correo registrado",
        )
        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="••••••••",
        )
        recordar = st.checkbox("Mantener sesión activa en este equipo", value=True)
        enviar = st.form_submit_button(
            "Acceder al sistema",
            type="primary",
            width="stretch",
            disabled=bloqueado > 0,
        )

    if enviar:
        _procesar_login(identificador, password, recordar)

    if st.button(
        "¿Olvidaste tu contraseña?",
        type="tertiary",
        key="auth_ir_recuperar",
        width="stretch",
    ):
        _ir("recuperar")

    st.html(
        '<div class="dss-auth-models">'
        '<div class="dss-auth-model-badge"><span>Modelo</span><b>EOQ · Wilson</b></div>'
        '<div class="dss-auth-model-badge"><span>Seguridad</span><b>Punto ROP</b></div>'
        '<div class="dss-auth-model-badge"><span>Auditoría</span><b>Pareto ABC</b></div>'
        "</div>"
    )


def _procesar_login(identificador: str, password: str, recordar: bool = True):
    if not identificador.strip() or not password:
        st.error("Por favor ingrese su usuario/correo y contraseña.")
        return

    user_id, registro = _buscar_usuario(identificador)
    clave_eval = user_id or identificador.strip().lower()

    try:
        db_persistencia.inicializar_db()
        seg_bloqueo_usr = db_persistencia.segundos_bloqueo_login_usuario(
            clave_eval, max_intentos=MAX_INTENTOS, ventana_seg=BLOQUEO_SEGUNDOS
        )
    except Exception:
        seg_bloqueo_usr = 0

    if seg_bloqueo_usr > 0:
        st.session_state["auth_bloqueo"] = time.time() + seg_bloqueo_usr
        st.error(
            f"🛡️ Cuenta protegida contra ataques de fuerza bruta / DDoS (máximo {MAX_INTENTOS} intentos). "
            f"Intente nuevamente en {_formatear_tiempo(seg_bloqueo_usr)}."
        )
        st.rerun()

    if registro and db_persistencia.verificar_password(password, registro["password"]):
        token = crear_jwt({"sub": user_id, "rol": registro["rol"], "nombre": registro["nombre"]})
        st.session_state.pop("alerta_enviada", None)
        st.session_state.update(
            autenticado=True,
            rol=registro["rol"],
            nombre=registro["nombre"],
            usuario=user_id,
            auth_token=token,
            sesion_persistente=recordar,
            auth_intentos=0,
            auth_bloqueo=0.0,
        )
        try:
            st.session_state["auth_refresh_token"] = db_persistencia.crear_refresh_token(user_id)
            db_persistencia.registrar_auditoria(
                user_id, registro.get("correo", ""), "LOGIN", "Autenticación exitosa (Web)", True
            )
        except Exception:
            st.session_state["auth_refresh_token"] = None
        st.rerun()

    try:
        db_persistencia.registrar_auditoria(
            clave_eval, identificador.strip(), "LOGIN", "Intento fallido (Web)", False
        )
    except Exception:
        pass
    st.session_state["auth_intentos"] += 1
    restantes = MAX_INTENTOS - st.session_state["auth_intentos"]
    if restantes <= 0:
        st.session_state["auth_intentos"] = 0
        st.session_state["auth_bloqueo"] = time.time() + BLOQUEO_SEGUNDOS
        try:
            db_persistencia.registrar_auditoria(
                clave_eval,
                identificador.strip(),
                "BLOQUEO_DDOS_LOGIN",
                f"Bloqueo de 5 min tras {MAX_INTENTOS} intentos fallidos",
                False,
            )
        except Exception:
            pass
        st.error(
            f"🛡️ Demasiados intentos fallidos ({MAX_INTENTOS}/{MAX_INTENTOS}). "
            f"Por seguridad Anti-DDoS, el acceso se bloqueó por 5 minutos."
        )
        st.rerun()

    st.error(
        f"Credenciales inválidas. Verifique sus datos ({restantes} intento restante antes del bloqueo de 5 min)."
    )


def _vista_recuperar():
    _cabecera(
        "Recuperación de acceso",
        "¿Olvidaste tu contraseña?",
        "Ingresa tu correo corporativo o ID de usuario para recibir un código de verificación temporal.",
        paso="Paso 1 de 3 · Identificación",
    )

    bloqueado_rec = _segundos_bloqueo_rec()
    if bloqueado_rec > 0:
        _render_reloj_bloqueo(
            "auth_rec_bloqueo",
            "Se alcanzó el límite máximo de 2 intentos de recuperación para proteger el servidor contra ataques DDoS. Espere a que el contador llegue a 00:00.",
        )

    with st.form("recuperar_form", border=False):
        identificador = st.text_input(
            "Correo electrónico o ID de usuario",
            placeholder="Ingrese su usuario o correo registrado",
        )
        enviar = st.form_submit_button(
            "Enviar código de recuperación",
            type="primary",
            width="stretch",
            disabled=bloqueado_rec > 0,
        )

    if enviar:
        valor = identificador.strip()
        if not valor:
            st.error("Ingrese su correo electrónico o ID de usuario.")
        elif "@" in valor and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", valor):
            st.error("El formato del correo electrónico no es válido.")
        else:
            encontrado, seg_bloq = _generar_codigo(valor)
            if seg_bloq > 0:
                st.error(
                    f"🛡️ Límite Anti-DDoS alcanzado ({MAX_INTENTOS} intentos en 5 minutos). "
                    f"Por seguridad, espere {_formatear_tiempo(seg_bloq)}."
                )
                st.rerun()
            elif not encontrado:
                rest = max(0, MAX_INTENTOS - st.session_state.get("auth_rec_intentos", 0))
                st.error(
                    f"No se encontró una cuenta asociada a los datos ingresados ({rest} intento restante)."
                )
            else:
                _ir("codigo")

    if st.button(
        "← Volver al inicio de sesión",
        type="tertiary",
        key="auth_volver_recuperar",
        width="stretch",
    ):
        _ir("login")


def _vista_codigo():
    _cabecera(
        "Verificación de seguridad",
        "Valida tu código temporal",
        f"Ingresa el código de {LONGITUD_CODIGO} dígitos enviado a tu bandeja corporativa.",
        paso="Paso 2 de 3 · Verificación",
    )

    recuperacion = st.session_state.get("auth_recuperacion")
    if not recuperacion:
        st.warning("No hay una solicitud de recuperación activa.")
        if st.button("Solicitar código", type="primary", width="stretch"):
            _ir("recuperar")
        return

    bloqueado_rec = _segundos_bloqueo_rec()
    if bloqueado_rec > 0:
        _render_reloj_bloqueo(
            "auth_rec_bloqueo",
            "Se alcanzó el límite máximo de 2 envíos de código en 5 minutos. El reenvío se habilitará al terminar el conteo.",
        )

    _render_panel_otp_vivo()

    with st.container(key="otp_input_wrap"):
        with st.form("codigo_form", border=False):
            codigo = st.text_input(
                "PIN de seguridad (6 dígitos)",
                max_chars=LONGITUD_CODIGO,
                placeholder="••••••",
            )
            enviar = st.form_submit_button(
                "Verificar código y continuar",
                type="primary",
                width="stretch",
            )

    if enviar:
        _verificar_codigo(codigo.strip())

    col_reenviar, col_volver = st.columns(2)
    with col_reenviar:
        if st.button(
            "Reenviar código",
            type="tertiary",
            key="auth_reenviar",
            width="stretch",
            disabled=bloqueado_rec > 0,
        ):
            ok_reenvio, seg_bloq = _generar_codigo(recuperacion["usuario"])
            if seg_bloq > 0:
                st.toast(
                    f"🛡️ Bloqueo Anti-DDoS: máximo {MAX_INTENTOS} envíos cada 5 minutos.",
                    icon="🛡️",
                )
            elif ok_reenvio:
                st.toast("Se generó y envió un segundo código de verificación (2/2).", icon="✉️")
            st.rerun()
    with col_volver:
        if st.button(
            "Cambiar cuenta",
            type="tertiary",
            key="auth_cambiar_usuario",
            width="stretch",
        ):
            _ir("recuperar")


def _verificar_codigo(codigo: str):
    recuperacion = st.session_state.get("auth_recuperacion")
    if not recuperacion or time.time() > recuperacion["expira"]:
        st.session_state["auth_recuperacion"] = None
        st.error("El código venció o no es válido. Solicite uno nuevo.")
        return

    if not codigo:
        st.error("Ingrese el código de 6 dígitos.")
        return

    if not secrets.compare_digest(recuperacion["codigo"], codigo):
        recuperacion["intentos"] += 1
        restantes = MAX_INTENTOS - recuperacion["intentos"]
        if restantes <= 0:
            st.session_state["auth_recuperacion"] = None
            st.session_state["auth_rec_bloqueo"] = time.time() + BLOQUEO_SEGUNDOS
            st.session_state["auth_vista"] = "recuperar"
            st.error(
                f"🛡️ Se superaron los {MAX_INTENTOS} intentos permitidos. "
                f"Recuperación bloqueada por 5 minutos (Anti-DDoS)."
            )
            st.rerun()
        else:
            st.error(f"Código incorrecto. Verifique e intente nuevamente ({restantes} intento restante).")
        return

    st.session_state["auth_vista"] = "nueva"
    st.rerun()


def _vista_nueva():
    _cabecera(
        "Actualización de credenciales",
        "Restablecer contraseña",
        f"Define una clave segura (mínimo {MIN_LONGITUD_PASSWORD} caracteres con letras y números).",
        paso="Paso 3 de 3 · Nueva clave",
    )

    recuperacion = st.session_state.get("auth_recuperacion")
    if not recuperacion:
        st.error("La sesión de recuperación expiró. Solicite un nuevo código.")
        if st.button("Volver a recuperar", type="primary", width="stretch"):
            _ir("recuperar")
        return

    with st.form("nueva_form", border=False):
        nueva = st.text_input(
            "Nueva contraseña",
            type="password",
            placeholder="Mínimo 8 caracteres alfanuméricos",
        )
        confirmacion = st.text_input(
            "Confirmar nueva contraseña",
            type="password",
            placeholder="Repite la nueva contraseña",
        )
        enviar = st.form_submit_button(
            "Guardar y restablecer contraseña",
            type="primary",
            width="stretch",
        )

    if enviar:
        _guardar_password(nueva, confirmacion)

    if st.button(
        "Cancelar y volver al login",
        type="tertiary",
        key="auth_cancelar_nueva",
        width="stretch",
    ):
        st.session_state.update(auth_recuperacion=None, auth_vista="login")
        st.rerun()


def _guardar_password(nueva: str, confirmacion: str):
    recuperacion = st.session_state.get("auth_recuperacion")
    if not recuperacion:
        st.error("La sesión de recuperación expiró. Solicite un nuevo código.")
        return

    error = _politica_password(nueva)
    if error:
        st.error(error)
        return
    if nueva != confirmacion:
        st.error("Las contraseñas ingresadas no coinciden.")
        return

    user_id = recuperacion["usuario"]
    db = _db_usuarios()
    registro = db.get(user_id) or {}
    if db_persistencia.verificar_password(nueva, registro.get("password") or ""):
        st.error("La nueva contraseña debe ser diferente a la contraseña actual.")
        return

    db_persistencia.actualizar_password(user_id, nueva)
    st.session_state.update(
        auth_recuperacion=None,
        auth_vista="login",
        auth_intentos=0,
        auth_bloqueo=0.0,
        auth_mensaje="Contraseña restablecida con éxito. Ya puedes iniciar sesión con tu nueva clave.",
    )
    st.rerun()


def _renovar_sesion():
    """Renueva el access token usando el refresh token almacenado en sesión."""
    token = st.session_state.get("auth_refresh_token")
    if not token:
        return False
    fila = db_persistencia.validar_refresh_token(token)
    if fila is None:
        return False
    usuario_id = fila["usuario_id"]
    usuario = db_persistencia.obtener_usuario(usuario_id) or {}
    db_persistencia.revocar_refresh_token(token)
    st.session_state["auth_refresh_token"] = db_persistencia.crear_refresh_token(usuario_id)
    st.session_state["auth_token"] = crear_jwt(
        {
            "sub": usuario_id,
            "rol": usuario.get("rol") or "Operaciones",
            "nombre": usuario.get("nombre") or "Usuario",
        }
    )
    return True


_VISTAS = {
    "login": _vista_login,
    "recuperar": _vista_recuperar,
    "codigo": _vista_codigo,
    "nueva": _vista_nueva,
}


def renderizar_login():
    st.html('<div class="dss-auth-spacer"></div>')
    _, centro, _ = st.columns([1, 1.15, 1])

    with centro:
        with st.container(key="auth_card"):
            uri_logo = (
                obtener_imagen_b64("rectangular")
                or obtener_imagen_b64("cuadrado")
                or obtener_imagen_b64("circular")
            )
            logo_html = (
                f'<div class="dss-auth-hero-box">'
                f'<img class="dss-auth-hero-img" src="{uri_logo}" alt="Inversiones D-02-04">'
                f"</div>"
                if uri_logo
                else ""
            )

            st.html(
                f'<div class="dss-auth-top-meta">'
                f'<span class="dss-live"><span class="dss-dot-live"></span> Sistema Operativo</span>'
                f'<span class="dss-auth-tag">DSS Core · LME</span>'
                f"</div>"
                f"{logo_html}"
            )

            _VISTAS.get(st.session_state["auth_vista"], _vista_login)()

            st.html(
                f'<div class="dss-auth-foot">'
                f'{chip("Conexión cifrada TLS", "success")}'
                f'<div class="dss-auth-foot-copy">Inversiones D-02-04, C.A. · Acceso exclusivo para personal autorizado</div>'
                f"</div>"
            )


def renderizar_perfil_usuario():
    nombre = st.session_state.get("nombre") or "Usuario"
    rol = st.session_state.get("rol") or "—"
    iniciales = "".join(parte[0] for parte in nombre.split()[:2]).upper() or "U"

    with st.sidebar:
        with st.container(key="sidebar_profile"):
            st.html(
                f'<div class="dss-profile">'
                f'<div class="dss-avatar">{iniciales}</div>'
                f"<div>"
                f'<div class="dss-profile-name">{nombre}</div>'
                f'<div class="dss-profile-role">Rol: <b>{rol}</b></div>'
                f"</div>"
                f"</div>"
            )

            if st.button("Cerrar sesión", width="stretch"):
                st.session_state.update(
                    autenticado=False,
                    rol=None,
                    nombre=None,
                    usuario=None,
                    auth_token=None,
                    auth_refresh_token=None,
                    auth_vista="login",
                )
                st.rerun()

            if st.button("Renovar sesión", width="stretch"):
                if _renovar_sesion():
                    st.toast("Sesión renovada exitosamente.", icon="✅")
                else:
                    st.toast("La sesión expiró. Inicie acceso nuevamente.", icon="⚠️")
                st.rerun()

        st.html(
            f'<div class="dss-side-footer">'
            f'<div class="dss-side-status"><span class="dss-dot-live"></span> '
            f"Mercado conectado</div>"
            f'<div style="margin-top:6px;">DSS Core · v2.4</div>'
            f"</div>"
        )
