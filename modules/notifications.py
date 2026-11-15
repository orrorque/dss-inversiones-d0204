import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st

# ---------------------------------------------------------------------------
# Configuración SMTP del servidor de correos corporativo (DSS · Inversiones D-02-04)
# ---------------------------------------------------------------------------
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_USER = "dinversionesd0204@gmail.com"
DEFAULT_SMTP_PASS = "cmmixrqqfdthkgkh"
DEFAULT_SMTP_FROM = "dinversionesd0204@gmail.com"
DEFAULT_ALERT_EMAIL = "dinversionesd0204@gmail.com"
CODIGO_VALIDO_SEGUNDOS = 300


def _leer_config(nombre: str, default: str = "") -> str:
    """Lee la configuración desde variables de entorno, secrets.toml o valor por defecto."""
    env_val = os.getenv(nombre.upper()) or os.getenv(nombre.lower())
    if env_val and str(env_val).strip():
        return str(env_val).strip()
    try:
        valor = st.secrets.get(nombre.lower(), None) or st.secrets.get(nombre.upper(), None)
        if valor and str(valor).strip():
            return str(valor).strip()
    except Exception:
        pass
    return str(default).strip()


def obtener_config_smtp() -> dict:
    """Obtiene la configuración SMTP evaluada dinámicamente en cada envío."""
    host = _leer_config("smtp_host", DEFAULT_SMTP_HOST)
    port_str = _leer_config("smtp_port", str(DEFAULT_SMTP_PORT))
    try:
        port = int(port_str)
    except ValueError:
        port = DEFAULT_SMTP_PORT
    user = _leer_config("smtp_user", DEFAULT_SMTP_USER)
    # Gmail App Passwords funcionan mejor sin espacios internos
    raw_pass = _leer_config("smtp_pass", DEFAULT_SMTP_PASS)
    password = raw_pass.replace(" ", "") if "gmail.com" in host.lower() else raw_pass
    sender = _leer_config("smtp_from", user or DEFAULT_SMTP_FROM)
    tls = _leer_config("smtp_tls", "true").lower() in ("1", "true", "yes", "on")
    destino_alerta = _leer_config("alert_email_destino", DEFAULT_ALERT_EMAIL)
    return {
        "host": host,
        "port": port,
        "user": user,
        "pass": password,
        "from": sender,
        "tls": tls,
        "alert_to": destino_alerta,
    }


def email_alerta_configurado() -> bool:
    """True cuando el servidor SMTP y credenciales de salida están operativos."""
    cfg = obtener_config_smtp()
    return bool(cfg["host"] and cfg["user"] and cfg["pass"])


def _normalizar_destinatario(destinatario: str, fallback: str) -> str:
    """Si el correo tiene el dominio ficticio @d-02-04.com, redirige al correo corporativo Gmail activo."""
    limpio = (destinatario or "").strip()
    if not limpio or limpio.lower().endswith("@d-02-04.com"):
        return fallback
    return limpio


def _enviar_email_alerta(subject: str, cuerpo: str, destinatario: str, cuerpo_html: str = None) -> bool:
    """Envía un correo corporativo vía SMTP (TLS/STARTTLS) con soporte texto plano y HTML."""
    cfg = obtener_config_smtp()
    if not cfg["host"] or not cfg["user"] or not cfg["pass"]:
        return False

    destino_real = _normalizar_destinatario(destinatario, cfg["alert_to"])
    if not destino_real:
        return False

    try:
        if cuerpo_html:
            mensaje = MIMEMultipart("alternative")
            mensaje.attach(MIMEText(cuerpo, "plain", "utf-8"))
            mensaje.attach(MIMEText(cuerpo_html, "html", "utf-8"))
        else:
            mensaje = MIMEText(cuerpo, "plain", "utf-8")

        mensaje["Subject"] = subject
        mensaje["From"] = f"DSS Inversiones D-02-04 <{cfg['from']}>"
        mensaje["To"] = destino_real

        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
            server.ehlo()
            if cfg["tls"]:
                server.starttls()
                server.ehlo()
            server.login(cfg["user"], cfg["pass"])
            server.sendmail(cfg["from"], [destino_real], mensaje.as_string())
        return True
    except Exception as exc:
        print(f"[DSS SMTP ERROR] No se pudo enviar correo a {destino_real}: {exc}")
        return False


def enviar_alerta_quiebre(df_resultados, email_destino: str = None) -> bool:
    """Envía el reporte ejecutivo de alerta de quiebre/umbral crítico vía SMTP."""
    criticos = df_resultados[df_resultados["Estatus"] == "CRÍTICO"]
    if criticos.empty:
        return False

    cfg = obtener_config_smtp()
    destino = _normalizar_destinatario(email_destino, cfg["alert_to"])

    lineas_txt = []
    filas_html = []
    for _, row in criticos.head(15).iterrows():
        cal = row.get("Calibre")
        stock = float(row.get("Stock Físico") or 0.0)
        rop = float(row.get("Punto de Quiebre (ROP)") or 0.0)
        deficit = float(row.get("Déficit Quiebre (kg)") or max(0.0, rop - stock))
        eoq = float(row.get("Sugerencia Compra (EOQ)") or 0.0)
        inv = float(row.get("Inversión Orden ($)") or 0.0)
        lineas_txt.append(
            f"- {cal}: Stock {stock:,.1f} kg | ROP {rop:,.1f} kg | Déficit {deficit:,.1f} kg | Lote EOQ {eoq:,.1f} kg (${inv:,.2f} USD)"
        )
        filas_html.append(
            f"<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #1E293B;font-weight:700;color:#F8FAFC;'>{cal}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #1E293B;color:#CBD5E1;text-align:right;'>{stock:,.1f} kg</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #1E293B;color:#CBD5E1;text-align:right;'>{rop:,.1f} kg</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #1E293B;color:#FF6B6B;font-weight:700;text-align:right;'>-{deficit:,.1f} kg</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #1E293B;color:#38BDF8;font-weight:700;text-align:right;'>{eoq:,.1f} kg</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #1E293B;color:#34D399;font-weight:700;text-align:right;'>${inv:,.2f}</td>"
            f"</tr>"
        )

    total_criticos = len(criticos)
    deficit_total = float(criticos["Déficit Quiebre (kg)"].sum()) if "Déficit Quiebre (kg)" in criticos else 0.0
    inversion_total = float(criticos["Inversión Orden ($)"].sum()) if "Inversión Orden ($)" in criticos else 0.0

    cuerpo = (
        "SISTEMA DSS · INVERSIONES D-02-04, C.A.\n"
        "ALERTA AUTOMÁTICA DE QUIEBRE LOGÍSTICO (STOCKOUT)\n"
        "============================================================\n\n"
        f"Calibres en estado CRÍTICO: {total_criticos} líneas\n"
        f"Déficit físico acumulado: {deficit_total:,.1f} kg\n"
        f"Presupuesto total sugerido (EOQ indexado LME): ${inversion_total:,.2f} USD\n\n"
        "Principales líneas afectadas:\n"
        + "\n".join(lineas_txt)
        + "\n\nIngrese al Centro de Control Logístico DSS para aprobar o gestionar las órdenes sugeridas.\n"
    )

    cuerpo_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:680px;margin:0 auto;background:#0A0F1A;color:#E6EDF7;border:1px solid #1E293B;border-radius:14px;overflow:hidden;">
      <div style="background:linear-gradient(90deg,#7F1D1D,#1E293B);padding:18px 24px;border-bottom:2px solid #FF6B6B;">
        <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#FCA5A5;font-weight:700;">Inversiones D-02-04, C.A. · DSS Core v2.4</div>
        <h2 style="margin:6px 0 0;color:#FFFFFF;font-size:20px;">⚠️ Alerta Crítica de Quiebre de Stock (ROP)</h2>
      </div>
      <div style="padding:20px 24px;">
        <p style="margin:0 0 14px;color:#CBD5E1;font-size:14px;line-height:1.5;">
          El motor matemático de inventario (<b>Wilson EOQ · Punto de Reorden ROP · Indexación Cobre LME</b>) ha detectado
          <b>{total_criticos} calibres</b> por debajo del umbral crítico de seguridad:
        </p>
        <div style="display:flex;gap:12px;margin-bottom:18px;background:#111A2B;padding:12px 16px;border-radius:10px;border:1px solid #1E293B;">
          <div style="flex:1;">
            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;">Líneas Críticas</div>
            <div style="font-size:18px;font-weight:800;color:#FF6B6B;">{total_criticos} SKUs</div>
          </div>
          <div style="flex:1;">
            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;">Déficit Acumulado</div>
            <div style="font-size:18px;font-weight:800;color:#F8FAFC;">{deficit_total:,.1f} kg</div>
          </div>
          <div style="flex:1;">
            <div style="font-size:11px;color:#94A3B8;text-transform:uppercase;">Inversión EOQ Sugerida</div>
            <div style="font-size:18px;font-weight:800;color:#34D399;">${inversion_total:,.2f} USD</div>
          </div>
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:12px;background:#111A2B;border-radius:8px;overflow:hidden;">
          <thead>
            <tr style="background:#17263C;color:#93C5FD;text-align:left;">
              <th style="padding:8px 10px;">Calibre</th>
              <th style="padding:8px 10px;text-align:right;">Stock</th>
              <th style="padding:8px 10px;text-align:right;">ROP</th>
              <th style="padding:8px 10px;text-align:right;">Déficit</th>
              <th style="padding:8px 10px;text-align:right;">Lote EOQ</th>
              <th style="padding:8px 10px;text-align:right;">Inversión</th>
            </tr>
          </thead>
          <tbody>
            {''.join(filas_html)}
          </tbody>
        </table>
        <p style="margin:18px 0 0;font-size:12px;color:#94A3B8;">
          Notificación automática despachada por el Sistema de Soporte a la Toma de Decisiones (DSS) · Inversiones D-02-04, C.A.
        </p>
      </div>
    </div>
    """

    return _enviar_email_alerta(
        subject=f"⚠️ URGENTE · DSS Inversiones D-02-04 · {total_criticos} calibres en Quiebre de Stock",
        cuerpo=cuerpo,
        destinatario=destino,
        cuerpo_html=cuerpo_html,
    )


def enviar_codigo_recuperacion(usuario: str, correo: str, codigo: str) -> bool:
    """Envía el código temporal de verificación de acceso al correo del usuario."""
    cfg = obtener_config_smtp()
    destino = _normalizar_destinatario(correo, cfg["alert_to"])
    asunto = f"🔐 Código de verificación DSS ({codigo}) · Inversiones D-02-04"
    cuerpo = (
        "SISTEMA DSS - INVERSIONES D-02-04, C.A.\n\n"
        "VERIFICACIÓN DE SEGURIDAD · RECUPERACIÓN DE ACCESO\n"
        "==================================================\n\n"
        f"Usuario solicitado: {usuario}\n"
        f"Código de verificación (6 dígitos): {codigo}\n\n"
        f"Este código es válido por {CODIGO_VALIDO_SEGUNDOS // 60} minutos ({CODIGO_VALIDO_SEGUNDOS} segundos).\n"
        "Ingrese estos 6 dígitos en la pantalla de validación del portal DSS para restablecer su contraseña.\n\n"
        "Si usted no solicitó este código, ignore este mensaje.\n"
    )
    cuerpo_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;background:#0A0F1A;color:#E6EDF7;border:1px solid #1E293B;border-radius:14px;overflow:hidden;">
      <div style="background:linear-gradient(90deg,#17263C,#0E1727);padding:18px 24px;border-bottom:2px solid #F2B45C;">
        <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#F2B45C;font-weight:700;">Inversiones D-02-04, C.A. · Seguridad DSS</div>
        <h2 style="margin:6px 0 0;color:#FFFFFF;font-size:19px;">Código de Verificación de Acceso</h2>
      </div>
      <div style="padding:22px 24px;text-align:center;">
        <p style="margin:0 0 14px;color:#CBD5E1;font-size:14px;line-height:1.5;">
          Se ha solicitado un restablecimiento de contraseña para la cuenta <b>{usuario}</b>.
          Utilice el siguiente código temporal de verificación:
        </p>
        <div style="display:inline-block;margin:12px 0 16px;padding:12px 28px;border-radius:10px;background:#111A2B;border:1px solid #F2B45C;color:#F7D9A8;font-size:28px;font-weight:800;letter-spacing:8px;">
          {codigo}
        </div>
        <p style="margin:0;color:#94A3B8;font-size:12px;">
          Vigencia: <b>5 minutos ({CODIGO_VALIDO_SEGUNDOS} segundos)</b>.<br>
          Si no solicitó este cambio, puede ignorar este correo de forma segura.
        </p>
      </div>
    </div>
    """
    return _enviar_email_alerta(
        subject=asunto,
        cuerpo=cuerpo,
        destinatario=destino,
        cuerpo_html=cuerpo_html,
    )


def procesar_alertas_automaticas(df_resultados, email_destino: str = None, forzar: bool = False) -> bool:
    """Procesa la alerta de quiebre y envía el correo operativo vía SMTP."""
    criticos = df_resultados[df_resultados["Estatus"] == "CRÍTICO"]

    if criticos.empty:
        return False

    if not forzar and st.session_state.get("alerta_enviada") is True:
        return True

    cfg = obtener_config_smtp()
    destino = _normalizar_destinatario(email_destino, cfg["alert_to"])
    enviado = enviar_alerta_quiebre(df_resultados, destino)

    if enviado:
        st.session_state["alerta_enviada"] = True
        st.session_state["ultimo_correo_alerta"] = destino
        st.toast(f"📨 Alerta operativa de Stockout enviada por correo a {destino}.", icon="✅")
    else:
        st.session_state["alerta_enviada"] = False
        st.toast(
            f"⚠️ No se pudo despachar el correo a {destino}. Verifique la conexión SMTP.",
            icon="⚠️",
        )
    return enviado
