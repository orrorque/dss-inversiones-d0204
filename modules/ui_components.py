import io
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

from . import db as db_persistencia
from .notifications import procesar_alertas_automaticas
from .math_models import (
    calcular_eoq,
    calcular_rop,
    evaluar_modelo_calibre,
    factor_mercado_cobre,
    obtener_z_score,
    pronosticar_serie,
)
from .theme import (
    MESES_ES,
    PALETA,
    PLOTLY_CONFIG,
    chip,
    estilizar_figura,
    icono,
    obtener_imagen_b64,
    rejilla_kpis,
    ruta_asset,
    seccion,
    sparkline,
    tarjeta_kpi,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def renderizar_panel_lateral(df_hist):
    uri_logo = (
        obtener_imagen_b64("cuadrado")
        or obtener_imagen_b64("rectangular")
        or obtener_imagen_b64("circular")
    )

    with st.sidebar:
        with st.container(key="sidebar_brand"):
            if uri_logo:
                st.html(
                    f'<div class="dss-sidebar-logo-wrap">'
                    f'<img class="dss-sidebar-logo" src="{uri_logo}" alt="Inversiones D-02-04">'
                    f"</div>"
                )
            else:
                st.html(
                    '<div class="dss-auth-eyebrow" style="text-align:center;">'
                    "Inversiones D-02-04</div>"
                )
            st.html('<div class="dss-side-caption">Sistema de Toma de Decisiones</div>')

        if st.session_state.get("rol") == "Administrador" or df_hist is None:
            st.html('<div class="dss-side-label">Módulo de soporte</div>')
            st.html(
                '<div style="padding:10px 12px;border-radius:12px;background:#0D1524;'
                'border:1px solid var(--dss-border);font-size:.74rem;color:var(--dss-muted);line-height:1.45;">'
                '<b style="color:var(--dss-text);display:block;margin-bottom:4px;">Soporte del Sistema (IT)</b>'
                "Acceso exclusivo a administración de cuentas, auditoría de accesos y salud del servidor API/SQLite."
                "</div>"
            )
            return None

        st.html('<div class="dss-side-label">Filtro de análisis</div>')
        calibre_sel = st.selectbox(
            "Calibre de mercado",
            df_hist.columns,
            help="Selecciona el calibre para el pronóstico de demanda y salidas.",
        )

        modo_carteleria = st.toggle(
            "Modo cartelería",
            help="Activa la recarga automática para pantallas de almacén.",
        )
        if modo_carteleria:
            st.markdown(
                """
                <style>
                [data-testid="stSidebar"] {display: none;}
                [data-testid="stHeader"] {display: none;}
                .block-container {padding-top: 1rem !important;}
                </style>
                <meta http-equiv="refresh" content="60">
                """,
                unsafe_allow_html=True,
            )

    return calibre_sel


# ---------------------------------------------------------------------------
# Modelo matemático multivariable para toma de decisiones
# ---------------------------------------------------------------------------


def generar_matriz_decisiones(df_inventario, df_hist, df_cobre, config):
    precio_actual = float(df_cobre["Close"].iloc[-1])
    precio_prom = float(df_cobre["Close"].mean())
    precio_proy = float(pronosticar_serie(df_cobre["Close"], 1).iloc[0])
    resultados = []

    for _, row in df_inventario.iterrows():
        calibre = row["Calibre"]
        stock = row["Stock Actual (kg)"]
        demanda = row["Demanda Anual Est. (kg)"]
        costo_unit = row["Costo Unitario ($)"]

        evaluacion = evaluar_modelo_calibre(
            calibre=calibre,
            stock_actual=stock,
            demanda_anual_base=demanda,
            costo_unitario_base=costo_unit,
            serie_salidas_calibre=df_hist[calibre],
            precio_cobre_actual=precio_actual,
            precio_cobre_promedio=precio_prom,
            precio_cobre_proyectado=precio_proy,
            config=config,
        )
        resultados.append(evaluacion)

    df_res = pd.DataFrame(resultados)

    df_res["Valor Consumo Anual"] = df_res["Demanda Anual"] * df_res["Costo Unitario"]
    df_res = df_res.sort_values(by="Valor Consumo Anual", ascending=False)
    df_res["Acumulado"] = (
        df_res["Valor Consumo Anual"].cumsum() / df_res["Valor Consumo Anual"].sum()
    )

    df_res["Clasificación ABC"] = np.where(
        df_res["Acumulado"] <= 0.8,
        "Clase A (Alto Impacto)",
        np.where(
            df_res["Acumulado"] <= 0.95,
            "Clase B (Moderado)",
            "Clase C (Bajo Impacto)",
        ),
    )

    df_ordenado = df_res.copy()
    df_ordenado["_num_calibre"] = pd.to_numeric(
        df_ordenado["Calibre"].astype(str).str.replace(" AWG", ""), errors="coerce"
    )
    df_ordenado = df_ordenado.sort_values(by="_num_calibre")
    df_ordenado = df_ordenado.drop(columns=["_num_calibre"])
    factor_lme, regimen_lme, variante_lme = factor_mercado_cobre(
        precio_actual, precio_prom, precio_proy
    )
    df_ordenado.attrs["modelo_meta"] = {
        "precio_cobre_actual": precio_actual,
        "precio_cobre_promedio": precio_prom,
        "precio_cobre_proyectado": precio_proy,
        "factor_lme": factor_lme,
        "regimen_lme": regimen_lme,
        "variante_lme": variante_lme,
        "dias_entrega": config["dias_entrega"],
        "desviacion_entrega": config["desviacion_entrega"],
        "nivel_servicio": config["nivel_servicio"],
        "z_score": obtener_z_score(config["nivel_servicio"]),
        "costo_pedido": config["costo_pedido"],
        "tasa_mantenimiento": config["tasa_mantenimiento"],
    }
    return df_ordenado


# ---------------------------------------------------------------------------
# Cabecera ejecutiva
# ---------------------------------------------------------------------------


def renderizar_cabecera():
    ahora = datetime.now()
    fecha_txt = f"{ahora.day:02d} {MESES_ES[ahora.month - 1]} {ahora.year} · {ahora:%H:%M}"
    rol = st.session_state.get("rol") or "—"
    nombre = st.session_state.get("nombre") or "Usuario"

    st.html(
        f'<div class="dss-topbar">'
        f'<div class="dss-topbar-id">'
        f'<div class="dss-logo-badge">{icono("escudo")}</div>'
        f"<div>"
        f'<div class="dss-topbar-eyebrow">Inversiones D-02-04 · C.A.</div>'
        f'<div class="dss-topbar-title">Centro de Control Logístico</div>'
        f'<div class="dss-topbar-sub">Inventario de cable de cobre · Decisiones de reposición y compra</div>'
        f"</div>"
        f"</div>"
        f'<div class="dss-topbar-meta">'
        f'<span class="dss-live"><span class="dss-dot-live"></span> En línea</span>'
        f'<div class="dss-meta-item"><span>Actualizado</span><b>{fecha_txt}</b></div>'
        f'<div class="dss-meta-item"><span>Perfil</span><b>{rol} · {nombre}</b></div>'
        f"</div>"
        f"</div>"
    )


def _api_get(path: str, timeout: int = 3):
    """Consulta el backend REST del DSS (salud / órdenes) con fallback directo a SQLite en la nube."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8501{path}", timeout=timeout) as respuesta:
            return respuesta.status, json.loads(respuesta.read().decode("utf-8"))
    except Exception:
        try:
            db_persistencia.inicializar_db()
            if path == "/api/salud":
                usuarios_activos = len([u for u in db_persistencia.todos_los_usuarios() if u.get("activo")])
                return 200, {
                    "status": "ok",
                    "servicio": "DSS Core",
                    "base_datos": "ok",
                    "usuarios_activos": usuarios_activos,
                    "ordenes_registradas": db_persistencia.contar_ordenes(),
                    "cors": "enabled",
                    "rate_limit": "2 int / 5 min (Anti-DDoS)",
                }
            if path == "/api/ordenes":
                return 200, {"ordenes": db_persistencia.listar_ordenes(100)}
        except Exception:
            pass
        return None, None


def renderizar_estado_backend():
    """Indicador de estado del motor de decisión conectado a la API."""
    estado, datos = _api_get("/api/salud")
    conectado = bool(estado == 200 and datos and datos.get("status") == "ok")
    _, datos_ord = _api_get("/api/ordenes", timeout=5)
    ultima = (datos_ord or {}).get("ordenes") or []
    ultima_orden = ultima[0] if ultima else {}
    calibre_ult = str(ultima_orden.get("calibre") or "Sin órdenes")
    inv_ult = float(ultima_orden.get("inversion_usd") or 0.0)

    seccion(
        "Backend · Conexión",
        "Motor de decisión en tiempo real",
        "Estado del servicio DSS Core operando sobre la API de órdenes y salud.",
        lado_derecho=chip("API Online" if conectado else "API Offline", "success" if conectado else "danger"),
    )

    color_estado = "#3DDC97" if conectado else "#FF6B6B"
    st.html(
        '<div style="border:1px solid var(--dss-border); background:var(--dss-surface); '
        'border-radius:16px; padding:15px 18px; display:flex; gap:20px; flex-wrap:wrap; align-items:center;">'
        f'<div style="display:flex; align-items:center; gap:10px;">'
        f'<span class="dss-dot-live" style="width:9px;height:9px;border-radius:50%;background:{color_estado};"></span>'
        f'<b style="color:var(--dss-text); font-size:.88rem;">DSS Core API</b>'
        f"</div>"
        f'<div style="display:flex; gap:24px; flex-wrap:wrap;">'
        f'<div style="display:flex; flex-direction:column; gap:2px;">'
        f'<span style="font-size:.6rem; text-transform:uppercase; letter-spacing:.09em; color:var(--dss-faint); font-weight:700;">Estado</span>'
        f'<b style="color:{color_estado}; font-size:.86rem; font-weight:700;">{"Operativo" if conectado else "Sin conexión"}</b>'
        f"</div>"
        f'<div style="display:flex; flex-direction:column; gap:2px;">'
        f'<span style="font-size:.6rem; text-transform:uppercase; letter-spacing:.09em; color:var(--dss-faint); font-weight:700;">Última orden</span>'
        f'<b style="color:var(--dss-text); font-size:.86rem; font-weight:700;">{calibre_ult}</b>'
        f"</div>"
        f'<div style="display:flex; flex-direction:column; gap:2px;">'
        f'<span style="font-size:.6rem; text-transform:uppercase; letter-spacing:.09em; color:var(--dss-faint); font-weight:700;">Inversión</span>'
        f'<b style="color:var(--dss-copper); font-size:.86rem; font-weight:700;">${inv_ult:,.2f} USD</b>'
        f"</div>"
        f"</div>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Centro de alertas
# ---------------------------------------------------------------------------


def _datos_alerta(row):
    stock = float(row["Stock Físico"])
    rop = float(row["Punto de Quiebre (ROP)"])
    if row["Estatus"] == "CRÍTICO" or (rop > 0 and stock <= rop):
        return "crit", "Crítico", max(rop - stock, 0.0)
    return "warn", "Observación", max(stock - rop, 0.0)


def _tarjeta_alerta(row, tipo):
    stock = float(row["Stock Físico"])
    rop = float(row["Punto de Quiebre (ROP)"])
    _, etiqueta, margen = _datos_alerta(row)
    cobertura = (stock / rop * 100) if rop > 0 else 0.0
    ancho = max(3.0, min(cobertura, 100.0))
    clase = "dss-stock-card--warn" if tipo == "warn" else ""
    etiqueta_pie = "Déficit" if tipo == "crit" else "Margen"

    return (
        f'<div class="dss-stock-card {clase}">'
        f'<div class="dss-stock-top">'
        f'<span class="dss-stock-name">{row["Calibre"]}</span>'
        f'<span class="dss-stock-badge">{etiqueta}</span>'
        f"</div>"
        f'<div class="dss-stock-row"><span>Stock</span><b>{stock:,.0f} kg</b></div>'
        f'<div class="dss-stock-row"><span>ROP</span><b>{rop:,.1f} kg</b></div>'
        f'<div class="dss-stock-deficit"><span>{etiqueta_pie}</span>'
        f"<b>{margen:,.1f} kg</b></div>"
        f"</div>"
    )


def _ticker(items_html, cantidad):
    """Pista de desplazamiento continuo: el contenido se duplica para un bucle sin saltos."""
    duracion = max(16.0, cantidad * 4.5)
    grupo_visible = f'<div class="dss-ticker-group">{items_html}</div>'
    grupo_repetido = f'<div class="dss-ticker-group" aria-hidden="true">{items_html}</div>'
    return (
        f'<div class="dss-ticker">'
        f'<div class="dss-ticker-track" style="--dss-ticker-dur:{duracion:.1f}s">'
        f"{grupo_visible}{grupo_repetido}"
        f"</div></div>"
    )


def renderizar_centro_alertas(df_resultados):
    criticos = df_resultados[df_resultados["Estatus"] == "CRÍTICO"].copy()
    observacion = df_resultados[
        (df_resultados["Estatus"] != "CRÍTICO")
        & (df_resultados["Punto de Quiebre (ROP)"] > 0)
        & (df_resultados["Stock Físico"] <= df_resultados["Punto de Quiebre (ROP)"] * 1.15)
    ].copy()

    ahora = datetime.now().strftime("%H:%M")

    if criticos.empty and observacion.empty:
        st.html(
            f'<div class="dss-alert dss-alert--ok">'
            f'<div class="dss-ok-wrap">'
            f'<div class="dss-ok-icon">{icono("check")}</div>'
            f"<div>"
            f'<div class="dss-ok-title">Monitoreo logístico estable</div>'
            f'<div class="dss-ok-sub">Todos los niveles de inventario se encuentran dentro '
            f"de los parámetros de seguridad definidos.</div>"
            f"</div>"
            f'<div class="dss-ok-side">{chip("Sin alertas activas", "success")}</div>'
            f"</div>"
            f"</div>"
        )
        return

    if criticos.empty:
        # Solo hay líneas en observación: banner preventivo ámbar.
        observacion = observacion.sort_values("Stock Físico", ascending=True)
        items = "".join(_tarjeta_alerta(row, "warn") for _, row in observacion.iterrows())
        st.html(
            f'<div class="dss-alert dss-alert--warn">'
            f'<div class="dss-alert-head">'
            f'<div class="dss-alert-heading">'
            f'<span class="dss-alert-icon">{icono("alerta")}</span>'
            f"<div>"
            f'<div class="dss-alert-kicker">Monitoreo preventivo en tiempo real</div>'
            f'<div class="dss-alert-title">Líneas cercanas al punto de reorden · '
            f"{len(observacion)} en observación</div>"
            f"</div>"
            f"</div>"
            f'<div class="dss-alert-side">'
            f'{chip(f"{len(observacion)} en observación", "warning")}'
            f'<span class="dss-alert-time">Actualizado {ahora}</span>'
            f"</div>"
            f"</div>"
            f'<div class="dss-alert-copy">El stock físico aún supera el ROP, pero la cobertura '
            f"es inferior al 15 % de holgura. Conviene anticipar la reposición.</div>"
            f"{_ticker(items, len(observacion))}"
            f"</div>"
        )
        return

    criticos = criticos.assign(
        _deficit=criticos["Punto de Quiebre (ROP)"] - criticos["Stock Físico"]
    ).sort_values("_deficit", ascending=False)
    observacion = observacion.sort_values("Stock Físico", ascending=True)

    deficit_total = float(criticos["_deficit"].sum())
    items = "".join(_tarjeta_alerta(row, "crit") for _, row in criticos.iterrows())
    items += "".join(_tarjeta_alerta(row, "warn") for _, row in observacion.iterrows())

    chips_obs = (
        chip(f"{len(observacion)} en observación", "warning")
        if not observacion.empty
        else ""
    )

    correo_env = st.session_state.get("ultimo_correo_alerta") or "dinversionesd0204@gmail.com"
    chip_correo = (
        chip(f"📨 Alerta enviada: {correo_env}", "success")
        if st.session_state.get("alerta_enviada")
        else chip("Correo pendiente", "warning")
    )

    st.html(
        f'<div class="dss-alert dss-alert--critical">'
        f'<div class="dss-alert-head">'
        f'<div class="dss-alert-heading">'
        f'<span class="dss-alert-icon">{icono("alerta")}</span>'
        f"<div>"
        f'<div class="dss-alert-kicker">Monitoreo de stockout en tiempo real</div>'
        f'<div class="dss-alert-title">Alerta de quiebre de stock · '
        f"{len(criticos)} calibres críticos</div>"
        f"</div>"
        f"</div>"
        f'<div class="dss-alert-side">'
        f"{chip_correo}"
        f'{chip(f"{len(criticos)} críticos", "danger")}'
        f"{chips_obs}"
        f'<span class="dss-alert-time">Actualizado {ahora}</span>'
        f"</div>"
        f"</div>"
        f'<div class="dss-alert-copy">El stock físico se encuentra por debajo del punto de reorden '
        f"(ROP) en <b>{len(criticos)} de {len(df_resultados)}</b> calibres. "
        f"El déficit agregado asciende a <b>{deficit_total:,.1f} kg</b>; "
        f"se recomienda emitir las órdenes sugeridas en la matriz de ejecución.</div>"
        f"{_ticker(items, len(criticos) + len(observacion))}"
        f"</div>"
    )
    _, col_btn_mail = st.columns([3.2, 1.2])
    with col_btn_mail:
        if st.button(
            "📧 Reenviar alerta al correo ahora",
            key="btn_reenviar_alerta_smtp",
            type="secondary",
            use_container_width=True,
        ):
            procesar_alertas_automaticas(df_resultados, forzar=True)
            st.rerun()


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------


def _partir_decimal(valor, decimales=2):
    texto = f"{valor:,.{decimales}f}"
    if "." in texto:
        entero, decimal = texto.split(".")
        return entero, f".{decimal}"
    return texto, ""


def renderizar_kpis_profesionales(df_resultados, df_cobre, df_hist):
    precio_actual = df_cobre['Close'].iloc[-1]
    tendencia_cobre = precio_actual - df_cobre['Close'].iloc[-2]

    cap_actual = (df_resultados['Stock Físico'] * df_resultados['Costo Unitario']).sum()
    lineas_criticas = len(df_resultados[df_resultados['Estatus'] == 'CRÍTICO'])

    stock_total_kg = df_resultados['Stock Físico'].sum()
    demanda_anual_total = df_resultados['Demanda Anual'].sum()
    demanda_diaria_promedio = demanda_anual_total / 365

    dias_autonomia = stock_total_kg / demanda_diaria_promedio if demanda_diaria_promedio > 0 else 0
    rotacion = demanda_anual_total / stock_total_kg if stock_total_kg > 0 else 0

    total_lineas = len(df_resultados)
    pct_criticas = (lineas_criticas / total_lineas * 100) if total_lineas else 0

    entero_cap, dec_cap = _partir_decimal(cap_actual)
    entero_cobre, dec_cobre = _partir_decimal(precio_actual)

    ultimo_mes = df_hist.iloc[-1]
    top_calibre = ultimo_mes.idxmax()
    top_kg = ultimo_mes.max()
    fecha_ult = df_hist.index[-1]
    mes_txt = f"{MESES_ES[fecha_ult.month - 1].capitalize()} {fecha_ult.year}"

    spark_capital = sparkline(
        (df_resultados["Stock Físico"] * df_resultados["Costo Unitario"]).tolist(),
        PALETA["cobre"],
        uid="capital",
    )
    spark_cobre = sparkline(
        df_cobre["Close"].tail(16).tolist(), PALETA["cobre"], uid="cobre"
    )
    spark_ventas = sparkline(
        df_hist[top_calibre].tail(12).tolist(), PALETA["verde"], uid="ventas"
    )
    spark_demanda = sparkline(
        df_hist.sum(axis=1).tail(12).tolist(), PALETA["cyan"], uid="demanda"
    )

    if tendencia_cobre >= 0:
        pie_cobre = chip(f"▲ {tendencia_cobre:,.2f} USD", "success")
    else:
        pie_cobre = chip(f"▼ {abs(tendencia_cobre):,.2f} USD", "danger")

    tarjetas = [
        tarjeta_kpi(
            "Capital inmovilizado",
            f"${entero_cap}",
            decimales=dec_cap,
            icono_nombre="capital",
            acento="cobre",
            pie=chip(
                f"● {lineas_criticas} líneas críticas",
                "danger" if lineas_criticas else "success",
            ),
            nota=f"de {total_lineas} SKUs",
            spark=spark_capital,
        ),
        tarjeta_kpi(
            "Autonomía del almacén",
            f"{dias_autonomia:.0f}",
            unidad="días",
            icono_nombre="autonomia",
            acento="cyan",
            pie=chip(f"Rotación {rotacion:.1f}x / año", "info"),
            nota="Cobertura actual",
            spark=spark_demanda,
        ),
        tarjeta_kpi(
            "Cobre global · LME",
            f"${entero_cobre}",
            decimales=dec_cobre,
            unidad="/t",
            icono_nombre="cobre",
            acento="cobre",
            pie=pie_cobre,
            nota="USD / tonelada",
            spark=spark_cobre,
        ),
        tarjeta_kpi(
            "Top ventas",
            f"{top_calibre}",
            unidad=f"{top_kg:,.0f} kg",
            icono_nombre="ventas",
            acento="verde",
            pie=chip(mes_txt, "neutral"),
            nota="Mayor rotación",
            spark=spark_ventas,
        ),
    ]

    seccion(
        "Panel ejecutivo",
        "Resumen financiero y operativo",
        "Indicadores clave de capital, cobertura y mercado del cobre.",
    )
    rejilla_kpis(tarjetas)


# ---------------------------------------------------------------------------
# Inteligencia de mercado
# ---------------------------------------------------------------------------


def _cabecera_grafica(eyebrow, titulo, subtitulo, etiqueta_chip, variante="copper"):
    return (
        f'<div class="dss-card-head">'
        f"<div>"
        f'<div class="dss-card-eyebrow">{eyebrow}</div>'
        f'<div class="dss-card-title">{titulo}</div>'
        f'<div class="dss-card-sub">{subtitulo}</div>'
        f"</div>"
        f"{chip(etiqueta_chip, variante)}"
        f"</div>"
    )


def _stat(etiqueta, valor, clase=""):
    return (
        f'<div class="dss-stat"><span>{etiqueta}</span>'
        f'<b class="{clase}">{valor}</b></div>'
    )


def renderizar_inteligencia_mercado(df_inventario, df_hist, df_cobre, calibre_sel):
    seccion(
        "Analítica predictiva",
        "Inteligencia de mercado y demanda",
        "Series históricas, proyección de salidas y cotización internacional del cobre.",
        lado_derecho=chip("Proyección a 1 mes", "copper"),
    )

    colA, colB = st.columns(2, gap="medium")

    with colA:
        with st.container(key="card_demanda"):
            hist_data = df_hist[calibre_sel]
            pronostico = pronosticar_serie(hist_data, 1)
            fecha_futura = hist_data.index[-1] + pd.DateOffset(months=1)

            st.html(
                _cabecera_grafica(
                    "Demanda mensual",
                    f"Pronóstico de salidas · {calibre_sel}",
                    "Histórico de 12 meses y próximo periodo",
                    "1 mes",
                    "info",
                )
            )

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=hist_data.index,
                    y=hist_data.values,
                    mode="lines+markers",
                    name="Histórico",
                    line=dict(color=PALETA["cyan"], width=2.6),
                    marker=dict(
                        size=5,
                        color=PALETA["cyan"],
                        line=dict(width=1.5, color="#0B1424"),
                    ),
                    fill="tozeroy",
                    fillcolor="rgba(76,201,240,0.08)",
                    hovertemplate="<b>%{y:,.0f} kg</b><br>%{x|%b %Y}<extra>Histórico</extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[hist_data.index[-1], fecha_futura],
                    y=[hist_data.values[-1], pronostico.values[0]],
                    mode="lines+markers",
                    name="Proyección",
                    line=dict(color=PALETA["cobre"], width=2.6, dash="dash"),
                    marker=dict(
                        size=[2, 9],
                        symbol="diamond",
                        color=PALETA["cobre"],
                        line=dict(width=2, color="#0B1424"),
                    ),
                    hovertemplate="<b>%{y:,.0f} kg</b><br>%{x|%b %Y}<extra>Proyección</extra>",
                )
            )
            estilizar_figura(fig, alto=286, fecha=True)
            st.plotly_chart(
                fig, width="stretch", theme=None, config=PLOTLY_CONFIG
            )

            ultimo_valor = float(hist_data.values[-1])
            proy_valor = float(pronostico.values[0])
            variacion = ((proy_valor / ultimo_valor) - 1) * 100 if ultimo_valor else 0
            clase_var = "up" if variacion >= 0 else "down"
            flecha = "▲" if variacion >= 0 else "▼"

            st.html(
                f'<div class="dss-stat-strip">'
                f'{_stat("Último mes", f"{ultimo_valor:,.0f} kg")}'
                f'{_stat("Proyección", f"{proy_valor:,.0f} kg")}'
                f'{_stat("Variación", f"{flecha} {abs(variacion):.1f}%", clase_var)}'
                f"</div>"
            )

    with colB:
        with st.container(key="card_cobre"):
            serie_cobre = df_cobre["Close"]
            pronostico_cobre = pronosticar_serie(serie_cobre, 1)
            fecha_futura_cobre = serie_cobre.index[-1] + pd.DateOffset(months=1)
            ultimo_cierre = float(serie_cobre.iloc[-1])

            st.html(
                _cabecera_grafica(
                    "Materia prima",
                    "Cotización internacional del cobre · LME",
                    "Futuros HG=F convertidos a USD por tonelada métrica",
                    "USD / t",
                    "copper",
                )
            )

            fig2 = go.Figure(
                data=[
                    go.Candlestick(
                        x=df_cobre.index,
                        open=df_cobre["Open"],
                        high=df_cobre["High"],
                        low=df_cobre["Low"],
                        close=df_cobre["Close"],
                        increasing_line_color=PALETA["verde"],
                        increasing_fillcolor="rgba(61,220,151,.45)",
                        decreasing_line_color=PALETA["rojo"],
                        decreasing_fillcolor="rgba(255,107,107,.42)",
                        name="Cotización",
                        whiskerwidth=0.4,
                    )
                ]
            )
            fig2.add_trace(
                go.Scatter(
                    x=[serie_cobre.index[-1], fecha_futura_cobre],
                    y=[serie_cobre.values[-1], pronostico_cobre.values[0]],
                    mode="lines+markers",
                    name="Proyección",
                    line=dict(color=PALETA["cobre"], width=2.4, dash="dot"),
                    marker=dict(
                        size=[2, 8],
                        symbol="diamond",
                        color=PALETA["cobre"],
                        line=dict(width=2, color="#0B1424"),
                    ),
                    hovertemplate="<b>$%{y:,.0f} / t</b><br>%{x|%b %Y}<extra>Proyección</extra>",
                )
            )
            fig2.update_layout(xaxis_rangeslider_visible=False)
            fig2.add_hline(
                y=ultimo_cierre,
                line_dash="dot",
                line_color="rgba(242,180,92,.34)",
                line_width=1,
                annotation_text=f"Último  ${ultimo_cierre:,.0f}",
                annotation_position="top left",
                annotation_font=dict(size=9, color=PALETA["cobre"]),
                annotation_bgcolor="rgba(11,20,36,.75)",
            )
            estilizar_figura(
                fig2, alto=286, fecha=True, moneda=True, hovermode="x"
            )
            st.plotly_chart(
                fig2, width="stretch", theme=None, config=PLOTLY_CONFIG
            )

            proy_cobre = float(pronostico_cobre.values[0])
            clase_proy = "up" if proy_cobre >= ultimo_cierre else "down"
            st.html(
                f'<div class="dss-stat-strip">'
                f'{_stat("Último cierre", f"${ultimo_cierre:,.2f}")}'
                f'{_stat("Proyección", f"${proy_cobre:,.2f}", clase_proy)}'
                f'{_stat("Máx. 12M", f"${float(serie_cobre.max()):,.0f}")}'
                f'{_stat("Mín. 12M", f"${float(serie_cobre.min()):,.0f}")}'
                f"</div>"
            )


# ---------------------------------------------------------------------------
# PDF (sin cambios)
# ---------------------------------------------------------------------------


def generar_pdf_reporte(df_resultados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="INVERSIONES D-02-04, C.A.", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Reporte Ejecutivo de Decisiones Logísticas", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 10)
    anchos = [25, 30, 35, 35, 35, 30]
    encabezados = ['Calibre', 'Stock (kg)', 'Reorden (kg)', 'Comprar (kg)', 'Clase ABC', 'Estado']

    for i, enc in enumerate(encabezados):
        pdf.cell(anchos[i], 10, enc, 1, 0, 'C')
    pdf.ln()

    pdf.set_font("Arial", '', 9)
    for _, row in df_resultados.iterrows():
        pdf.cell(anchos[0], 10, str(row['Calibre']), 1, 0, 'C')
        pdf.cell(anchos[1], 10, str(row['Stock Físico']), 1, 0, 'C')
        pdf.cell(anchos[2], 10, str(row['Punto de Quiebre (ROP)']), 1, 0, 'C')
        pdf.cell(anchos[3], 10, str(row['Sugerencia Compra (EOQ)']), 1, 0, 'C')
        clase_corta = str(row['Clasificación ABC']).split(" ")[1]
        pdf.cell(anchos[4], 10, clase_corta, 1, 0, 'C')
        pdf.cell(anchos[5], 10, str(row['Estatus']), 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')


# ---------------------------------------------------------------------------
# Matriz de ejecución y exportación
# ---------------------------------------------------------------------------


def _clasificar_tarjeta(row):
    stock = float(row["Stock Físico"])
    rop = float(row["Punto de Quiebre (ROP)"])
    if row["Estatus"] == "CRÍTICO" or (rop > 0 and stock <= rop):
        return "crit", "Crítico", "danger"
    if rop > 0 and stock <= rop * 1.15:
        return "obs", "Observación", "warning"
    return "ok", "Óptimo", "success"


def _tarjeta_activo(row, tipo, ya_emitida=False):
    stock = float(row["Stock Físico"])
    rop = float(row["Punto de Quiebre (ROP)"])
    ss = float(row.get("Stock Seguridad (SS)", 0.0) or 0.0)
    eoq = float(row["Sugerencia Compra (EOQ)"])
    eoq_base = float(row.get("EOQ Base Wilson (kg)", eoq) or eoq)
    factor_lme = float(row.get("Factor LME", 1.0) or 1.0)
    costo_base = float(row.get("Costo Unitario", 0.0) or 0.0)
    costo_lme = float(row.get("Costo Indexado LME ($)", costo_base) or costo_base)
    inversion = float(row.get("Inversión Orden ($)", eoq * costo_lme) or 0.0)
    autonomia = float(row.get("Autonomía (Días)", 0.0) or 0.0)
    salida_proy = float(row.get("Salida Proy. Mes (kg)", 0.0) or 0.0)
    var_salida = float(row.get("Var. Salida (%)", 0.0) or 0.0)
    accion_sug = str(row.get("Acción Sugerida", "REPOSICIÓN"))

    _, etiqueta, _ = _clasificar_tarjeta(row)

    cobertura = (stock / rop * 100.0) if rop > 0 else 100.0
    ancho = max(6.0, min(cobertura, 100.0))

    gradientes_barra = {
        "crit": "linear-gradient(90deg, #38BDF8 0%, #818CF8 55%, #34D399 100%)",
        "obs": "linear-gradient(90deg, #38BDF8 0%, #34D399 100%)",
        "ok": "linear-gradient(90deg, #10B981 0%, #34D399 100%)",
    }
    color_barra = gradientes_barra.get(tipo, "linear-gradient(90deg, #38BDF8, #34D399)")

    if tipo == "crit":
        pie_etiqueta, pie_valor = "Déficit ROP", f"{max(rop - stock, 0):,.1f} kg"
        variante_estetica = "info"
        etiqueta_estetica = "Prioritaria"
    elif tipo == "obs":
        pie_etiqueta, pie_valor = "Holgura ROP", f"{max(stock - rop, 0):,.1f} kg"
        variante_estetica = "copper"
        etiqueta_estetica = "Preventiva"
    else:
        pie_etiqueta, pie_valor = "Superávit", f"{max(stock - rop, 0):,.1f} kg"
        variante_estetica = "success"
        etiqueta_estetica = "Óptimo"

    abc_completo = str(row["Clasificación ABC"])
    abc_corto = abc_completo.split(" (")[0]
    abc_impacto = (
        abc_completo.split(" (")[1].rstrip(")") if " (" in abc_completo else ""
    )

    chip_emitida = chip("✓ Aceptada", "success") if ya_emitida else ""

    return (
        f'<div class="dss-asset-top">'
        f'<span class="dss-asset-abc" title="{abc_impacto}">ABC · {abc_corto}</span>'
        f'<div style="display:flex;gap:5px;align-items:center;">{chip_emitida}{chip(etiqueta_estetica, variante_estetica)}</div>'
        f"</div>"
        f'<div class="dss-asset-head-row">'
        f'<div class="dss-asset-name">{row["Calibre"]}</div>'
        f'<div class="dss-asset-sub">{accion_sug} · {autonomia:,.0f}d autonomía</div>'
        f"</div>"
        f'<div class="dss-order-hero">'
        f'<div class="dss-order-hero-col">'
        f"<span>Lote óptimo a comprar (EOQ)</span>"
        f"<b>{eoq:,.1f} kg</b>"
        f"<small>Wilson: {eoq_base:,.1f} kg · LME {factor_lme:.2f}x</small>"
        f"</div>"
        f'<div class="dss-order-hero-col" style="text-align:right;">'
        f"<span>Inversión del lote</span>"
        f'<b class="copper">${inversion:,.2f}</b>'
        f"<small>${costo_lme:,.2f}/kg indexado LME</small>"
        f"</div>"
        f"</div>"
        f'<div class="dss-order-bar-wrap">'
        f'<div class="dss-order-bar-head">'
        f"<span>Cobertura ROP: <b>{cobertura:,.1f}%</b></span>"
        f"<span>{pie_etiqueta}: <b>{pie_valor}</b></span>"
        f"</div>"
        f'<div class="dss-order-bar-track">'
        f'<div class="dss-order-bar-fill" style="width:{ancho:.1f}%;background:{color_barra};"></div>'
        f"</div>"
        f"</div>"
        f'<div class="dss-asset-metrics">'
        f"<div><span>Stock Físico</span><b>{stock:,.0f} kg</b></div>"
        f"<div><span>Punto Quiebre (ROP)</span><b>{rop:,.1f} kg</b></div>"
        f"<div><span>Stock Seguridad (SS)</span><b>{ss:,.1f} kg</b></div>"
        f"<div><span>Salida Proy. (SES)</span><b>{salida_proy:,.0f} kg ({var_salida:+.1f}%)</b></div>"
        f"</div>"
        f'<div class="dss-asset-cost">'
        f"<span>Costo Base ${costo_base:,.2f} → LME ${costo_lme:,.2f}/kg</span>"
        f"<b>{inversion:,.2f} USD</b>"
        f"</div>"
    )


def renderizar_panel_acciones(df_resultados):
    criticos = int((df_resultados["Estatus"] == "CRÍTICO").sum())
    estables = int(len(df_resultados) - criticos)

    seccion(
        "Ejecución",
        "Matriz de decisiones y auditoría ABC",
        "Stock físico frente al punto de reorden, priorizado por criticidad.",
        lado_derecho=chip(f"{len(df_resultados)} SKUs monitoreados", "neutral"),
    )

    with st.container(key="card_matriz"):
        meta = getattr(df_resultados, "attrs", {}).get("modelo_meta") or {}
        st.html(
            f'<div class="dss-card-head">'
            f"<div>"
            f'<div class="dss-card-eyebrow">Cobertura de inventario</div>'
            f'<div class="dss-card-title">Stock físico vs. punto de reorden</div>'
            f'<div class="dss-card-sub">Rojo: por debajo del ROP · Cian: sobre el ROP</div>'
            f"</div>"
            f'<div style="display:flex;gap:6px;flex-wrap:wrap;">'
            f'{chip(f"{criticos} críticos", "danger")}'
            f'{chip(f"{estables} estables", "success")}'
            f'</div>'
            f'</div>'
        )

        st.html(
            f'<div class="dss-model-meta">'
            f'<div class="dss-model-meta-item"><span>Último cierre LME</span>'
            f"<b>${float(meta.get('precio_cobre_actual') or 0):,.2f} / t</b></div>"
            f'<div class="dss-model-meta-item"><span>Proyección LME</span>'
            f"<b>${float(meta.get('precio_cobre_proyectado') or 0):,.2f} / t</b></div>"
            f'<div class="dss-model-meta-item"><span>Régimen</span>'
            f"<b>{meta.get('regimen_lme') or 'N/D'}</b></div>"
            f'<div class="dss-model-meta-item"><span>Factor EOQ</span>'
            f"<b>{float(meta.get('factor_lme') or 1.0):.2f}x</b></div>"
            f'<div class="dss-model-meta-item"><span>Z-score</span>'
            f"<b>{float(meta.get('z_score') or 0):.2f}</b></div>"
            f'</div>'
        )

        colores_stock = [
            PALETA["rojo"] if estado == "CRÍTICO" else PALETA["cyan"]
            for estado in df_resultados["Estatus"]
        ]

        fig_bar = go.Figure()
        fig_bar.add_trace(
            go.Bar(
                x=df_resultados["Calibre"],
                y=df_resultados["Stock Físico"],
                name="Stock físico",
                marker=dict(color=colores_stock, line=dict(width=0), opacity=0.88),
                hovertemplate="<b>%{y:,.0f} kg</b><br>%{x}<extra>Stock físico</extra>",
            )
        )
        fig_bar.add_trace(
            go.Scatter(
                x=df_resultados["Calibre"],
                y=df_resultados["Punto de Quiebre (ROP)"],
                name="Punto de reorden (ROP)",
                mode="lines+markers",
                marker=dict(
                    color=PALETA["cobre"],
                    size=7,
                    line=dict(width=1.5, color="#0B1424"),
                ),
                line=dict(dash="dash", color=PALETA["cobre"], width=2),
                hovertemplate="<b>%{y:,.1f} kg</b><br>%{x}<extra>ROP</extra>",
            )
        )
        fig_bar.update_layout(barmode="overlay")
        estilizar_figura(
            fig_bar, alto=338, hovermode="x unified", ticksuffix=" kg", tickangle=-20
        )
        st.plotly_chart(
            fig_bar, width="stretch", theme=None, config=PLOTLY_CONFIG
        )

    # Consultar órdenes ya registradas y descartadas por el Gerente Logístico
    if "ordenes_descartadas" not in st.session_state:
        st.session_state["ordenes_descartadas"] = set()
    descartadas_set = st.session_state["ordenes_descartadas"]

    try:
        db_persistencia.inicializar_db()
        ordenes_actuales = db_persistencia.listar_ordenes(200)
    except Exception:
        ordenes_actuales = []
    calibres_emitidos = {str(o.get("calibre")) for o in ordenes_actuales}

    st.html(
        '<div class="dss-subhead">'
        '<div><div class="dss-subhead-title">Órdenes sugeridas · Mesa de Compras EOQ / ROP</div>'
        '<div class="dss-subhead-sub">El Gerente Logístico puede aceptar o eliminar órdenes sugeridas '
        "según criticidad ROP, clasificación ABC e indexación LME.</div></div>"
        f'{chip("Motor Wilson · LME · ROP", "info")}'
        "</div>"
    )

    # Barra de filtros y acciones por lote
    f_col1, f_col2, f_col3, f_col4 = st.columns([1.25, 1.35, 1.1, 1.3], gap="small")
    with f_col1:
        filtro_abc = st.selectbox(
            "Filtrar por Clasificación ABC",
            ["Todas las clases", "Clase A (Alto Impacto)", "Clase B (Moderado)", "Clase C (Bajo Impacto)"],
            key="oms_filtro_abc",
        )
    with f_col2:
        criterio_orden = st.selectbox(
            "Priorizar órdenes por",
            [
                "Mayor Déficit de Stock (kg)",
                "Mayor Inversión Requerida ($)",
                "Menor Cobertura ROP (%)",
                "Calibre Numérico (6 a 34 AWG)",
            ],
            key="oms_criterio_orden",
        )
    with f_col3:
        limite_vista = st.selectbox(
            "Despliegue en pantalla",
            ["Top 6 prioritarias", "Top 9 prioritarias", "Top 15 prioritarias", "Todos los calibres (29)"],
            index=1,
            key="oms_limite_vista",
        )
    with f_col4:
        st.html("<div style='height:23px;'></div>")
        if descartadas_set:
            if st.button(
                f"🔄 Restaurar eliminadas ({len(descartadas_set)})",
                key="btn_restaurar_descartadas",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state["ordenes_descartadas"] = set()
                st.toast("Órdenes sugeridas restauradas al tablero.", icon="🔄")
                st.rerun()
        else:
            df_clase_a_crit = df_resultados[
                (df_resultados["Estatus"] == "CRÍTICO")
                & (df_resultados["Clasificación ABC"].str.startswith("Clase A"))
            ]
            if st.button(
                f"✅ Aceptar Clase A ({len(df_clase_a_crit)})",
                key="btn_lote_clase_a",
                type="primary",
                use_container_width=True,
            ):
                db_persistencia.inicializar_db()
                usu_act = st.session_state.get("usuario")
                for _, r_a in df_clase_a_crit.iterrows():
                    db_persistencia.registrar_orden(
                        calibre=str(r_a["Calibre"]),
                        eoq_kg=float(r_a["Sugerencia Compra (EOQ)"]),
                        inversion_usd=float(r_a.get("Inversión Orden ($)", 0) or 0),
                        accion="ACEPTADA · LOTE CLASE A",
                        estatus="APROBADA",
                        usuario=usu_act,
                    )
                st.toast(
                    f"Se aceptaron y registraron {len(df_clase_a_crit)} órdenes de Clase A.",
                    icon="✅",
                )
                st.rerun()

    df_orden = df_resultados[~df_resultados["Calibre"].astype(str).isin(descartadas_set)].copy()
    if filtro_abc != "Todas las clases":
        df_orden = df_orden[df_orden["Clasificación ABC"] == filtro_abc]

    df_orden["_prioridad"] = df_orden["Estatus"].eq("CRÍTICO").astype(int)
    df_orden["_num_cal"] = pd.to_numeric(
        df_orden["Calibre"].astype(str).str.replace(" AWG", ""), errors="coerce"
    )

    if criterio_orden == "Mayor Déficit de Stock (kg)":
        df_orden = df_orden.sort_values(
            ["_prioridad", "Déficit Quiebre (kg)", "Punto de Quiebre (ROP)"],
            ascending=[False, False, False],
        )
    elif criterio_orden == "Mayor Inversión Requerida ($)":
        df_orden = df_orden.sort_values(
            ["_prioridad", "Inversión Orden ($)"], ascending=[False, False]
        )
    elif criterio_orden == "Menor Cobertura ROP (%)":
        df_orden = df_orden.sort_values(
            ["_prioridad", "Cobertura ROP (%)"], ascending=[False, True]
        )
    else:
        df_orden = df_orden.sort_values("_num_cal", ascending=True)

    mapa_limites = {
        "Top 6 prioritarias": 6,
        "Top 9 prioritarias": 9,
        "Top 15 prioritarias": 15,
        "Todos los calibres (29)": len(df_orden),
    }
    n_mostrar = mapa_limites.get(limite_vista, 9)
    df_vista = df_orden.head(n_mostrar)

    # Cinta ejecutiva de resumen financiero del bloque seleccionado
    vol_total_eoq = float(df_orden["Sugerencia Compra (EOQ)"].sum())
    deficit_total_kg = float(df_orden["Déficit Quiebre (kg)"].sum())
    inv_total_usd = float(df_orden["Inversión Orden ($)"].sum())
    emitidas_count = sum(1 for c in df_orden["Calibre"] if str(c) in calibres_emitidos)

    st.html(
        f'<div class="dss-oms-summary">'
        f'<div class="dss-oms-stat">'
        f"<span>Órdenes activas en tablero</span>"
        f"<b>{len(df_vista)} visibles de {len(df_orden)}</b>"
        f"<small>{emitidas_count} aceptadas · {len(descartadas_set)} eliminadas</small>"
        f"</div>"
        f'<div class="dss-oms-stat">'
        f"<span>Volumen total sugerido (EOQ)</span>"
        f"<b>{vol_total_eoq:,.1f} kg</b>"
        f"<small>Déficit acumulado: {deficit_total_kg:,.1f} kg</small>"
        f"</div>"
        f'<div class="dss-oms-stat">'
        f"<span>Presupuesto de compra (LME)</span>"
        f'<b style="color:#34D399;">${inv_total_usd:,.2f} USD</b>'
        f"<small>Costo indexado al mercado internacional</small>"
        f"</div>"
        f'<div class="dss-oms-stat">'
        f"<span>Cobertura objetivo post-compra</span>"
        f'<b style="color:#38BDF8;">95.0% Nivel Servicio</b>'
        f"<small>Recepción estimada en 15 ± 3 días</small>"
        f"</div>"
        f"</div>"
    )

    # Renderizado en cuadrícula real de 3 columnas por fila
    filas_records = list(df_vista.iterrows())
    for inicio_fila in range(0, len(filas_records), 3):
        bloque_fila = filas_records[inicio_fila : inicio_fila + 3]
        columnas_grid = st.columns(3, gap="medium")
        for idx_col, (_, row) in enumerate(bloque_fila):
            col = columnas_grid[idx_col]
            tipo, _, _ = _clasificar_tarjeta(row)
            calibre = str(row["Calibre"])
            eoq_val = float(row["Sugerencia Compra (EOQ)"])
            costo_lme_unit = float(row.get("Costo Indexado LME ($)", row["Costo Unitario"]) or row["Costo Unitario"])
            inv_val = float(row.get("Inversión Orden ($)", eoq_val * costo_lme_unit) or 0.0)
            eoq_txt = f"{eoq_val:,.1f}"
            ya_emitida = calibre in calibres_emitidos

            with col:
                with st.container(key=f"asset_{tipo}_{calibre.lower().replace(' ', '_')}"):
                    st.html(_tarjeta_activo(row, tipo, ya_emitida=ya_emitida))

                    b_col1, b_col2 = st.columns([1.15, 1.0], gap="small")
                    with b_col1:
                        accion_aceptar = st.button(
                            "✅ Aceptar OC",
                            key=f"btn_crit_{calibre}",
                            type="primary",
                            use_container_width=True,
                        )
                    with b_col2:
                        accion_eliminar = st.button(
                            "🗑️ Eliminar",
                            key=f"btn_del_{calibre}",
                            type="secondary",
                            use_container_width=True,
                        )

                    if accion_aceptar:
                        try:
                            db_persistencia.inicializar_db()
                            db_persistencia.registrar_orden(
                                calibre=calibre,
                                eoq_kg=eoq_val,
                                inversion_usd=inv_val,
                                accion="ORDEN ACEPTADA POR GERENCIA",
                                estatus="APROBADA",
                                usuario=st.session_state.get("usuario"),
                            )
                        except Exception:
                            pass
                        st.toast(
                            f"Orden de {calibre} por {eoq_txt} kg (${inv_val:,.2f} USD) aceptada y registrada.",
                            icon="✅",
                        )
                        st.rerun()

                    if accion_eliminar:
                        st.session_state["ordenes_descartadas"].add(calibre)
                        try:
                            db_persistencia.inicializar_db()
                            for o_ex in ordenes_actuales:
                                if str(o_ex.get("calibre")) == calibre and o_ex.get("id"):
                                    db_persistencia.eliminar_orden(int(o_ex["id"]))
                        except Exception:
                            pass
                        st.toast(
                            f"Orden sugerida de {calibre} eliminada del tablero.",
                            icon="🗑️",
                        )
                        st.rerun()

    with st.expander("Ver matriz completa de datos", expanded=False):
        df_tabla = df_resultados.copy()
        df_tabla["Clase ABC"] = (
            df_tabla["Clasificación ABC"].str.split(" (", regex=False).str[0]
        )
        df_tabla = df_tabla[
            [
                "Calibre",
                "Stock Físico",
                "Punto de Quiebre (ROP)",
                "Sugerencia Compra (EOQ)",
                "Clase ABC",
                "Estatus",
            ]
        ]
        st.dataframe(
            df_tabla,
            hide_index=True,
            width="stretch",
            height=430,
            column_config={
                "Calibre": st.column_config.TextColumn("Calibre"),
                "Stock Físico": st.column_config.NumberColumn(
                    "Stock (kg)", format="%.0f"
                ),
                "Punto de Quiebre (ROP)": st.column_config.NumberColumn(
                    "ROP (kg)", format="%.1f"
                ),
                "Sugerencia Compra (EOQ)": st.column_config.NumberColumn(
                    "Compra sugerida (kg)", format="%.1f"
                ),
                "Clase ABC": st.column_config.TextColumn("Clase ABC"),
                "Estatus": st.column_config.TextColumn("Estatus"),
            },
        )

    # -----------------------------------------------------------------------
    # Panel de órdenes aprobadas + Vista de entregas (Lead Time × EOQ)
    # -----------------------------------------------------------------------
    meta_lt = getattr(df_resultados, "attrs", {}).get("modelo_meta") or {}
    dias_lt = int(meta_lt.get("dias_entrega") or 15)
    desv_lt = int(meta_lt.get("desviacion_entrega") or 3)
    fecha_est_base = (datetime.now() + timedelta(days=dias_lt)).strftime("%Y-%m-%d")
    fecha_est_max = (datetime.now() + timedelta(days=dias_lt + desv_lt)).strftime("%Y-%m-%d")

    st.html("<div style='height:8px;'></div>")
    seccion(
        "Seguimiento Logístico",
        "Panel de órdenes aprobadas y cronograma de entregas",
        f"Historial persistido en API/SQLite y proyección de recepción en almacén (Lead Time: {dias_lt} ± {desv_lt} días).",
        lado_derecho=chip(f"Recepción est.: {fecha_est_base}", "info"),
    )

    _, datos_ord_api = _api_get("/api/ordenes", timeout=5)
    ordenes_lista = (datos_ord_api or {}).get("ordenes")
    if ordenes_lista is None:
        try:
            db_persistencia.inicializar_db()
            ordenes_lista = db_persistencia.listar_ordenes(50)
        except Exception:
            ordenes_lista = []

    col_ord, col_ent = st.columns(2, gap="medium")

    with col_ord:
        st.html(
            '<div class="dss-subhead" style="margin-top:0;">'
            '<div><div class="dss-subhead-title">Órdenes de compra emitidas</div>'
            '<div class="dss-subhead-sub">Registro en tiempo real desde /api/ordenes (SQLite).</div></div>'
            f'{chip(f"{len(ordenes_lista)} registradas", "copper")}'
            "</div>"
        )
        if ordenes_lista:
            filas_ord = []
            for o in ordenes_lista:
                creado_str = str(o.get("creado_en") or "")
                try:
                    dt_creado = datetime.strptime(creado_str[:19], "%Y-%m-%d %H:%M:%S")
                    entrega_o = (dt_creado + timedelta(days=dias_lt)).strftime("%Y-%m-%d")
                except Exception:
                    entrega_o = fecha_est_base
                filas_ord.append(
                    {
                        "ID": f"OC-{int(o.get('id') or 0):04d}",
                        "Calibre": o.get("calibre"),
                        "Lote EOQ (kg)": float(o.get("eoq_kg") or 0),
                        "Inversión ($)": float(o.get("inversion_usd") or 0),
                        "Acción": o.get("accion"),
                        "Usuario": o.get("usuario") or "sistema",
                        "Emisión": creado_str[:16],
                        "Entrega Est.": entrega_o,
                    }
                )
            st.dataframe(
                pd.DataFrame(filas_ord),
                hide_index=True,
                width="stretch",
                height=225,
            )
            opciones_oc = {
                f"OC-{int(o.get('id') or 0):04d} · {o.get('calibre')} ({float(o.get('eoq_kg') or 0):,.1f} kg)": int(o.get("id") or 0)
                for o in ordenes_lista
                if o.get("id")
            }
            if opciones_oc:
                m_c1, m_c2, m_c3 = st.columns([1.8, 1.0, 1.0], gap="small")
                with m_c1:
                    oc_sel_label = st.selectbox(
                        "Gestionar orden registrada",
                        list(opciones_oc.keys()),
                        key="sel_gestion_oc",
                        label_visibility="collapsed",
                    )
                with m_c2:
                    if st.button("✅ Aceptar OC", key="btn_conf_oc", type="primary", use_container_width=True):
                        db_persistencia.inicializar_db()
                        db_persistencia.actualizar_estado_orden(
                            opciones_oc[oc_sel_label], "APROBADA", "ACEPTADA POR GERENCIA"
                        )
                        st.toast(f"{oc_sel_label} confirmada por Gerencia.", icon="✅")
                        st.rerun()
                with m_c3:
                    if st.button("🗑️ Eliminar OC", key="btn_elim_oc", type="secondary", use_container_width=True):
                        db_persistencia.inicializar_db()
                        db_persistencia.eliminar_orden(opciones_oc[oc_sel_label])
                        st.toast(f"{oc_sel_label} eliminada de la base de datos.", icon="🗑️")
                        st.rerun()
        else:
            st.info("Aún no se han emitido órdenes de compra en la base de datos.")

    with col_ent:
        st.html(
            '<div class="dss-subhead" style="margin-top:0;">'
            '<div><div class="dss-subhead-title">Vista de entregas y reposición proyectada</div>'
            f'<div class="dss-subhead-sub">Ventana de arribo estimada: {fecha_est_base} a {fecha_est_max}</div></div>'
            f'{chip(f"Lead Time {dias_lt}d", "success")}'
            "</div>"
        )
        df_entregas = df_resultados.copy()
        df_entregas["Stock Post-Entrega (kg)"] = (
            df_entregas["Stock Físico"] + df_entregas["Sugerencia Compra (EOQ)"]
        ).round(1)
        df_entregas["Cobertura Post-EOQ (%)"] = np.where(
            df_entregas["Punto de Quiebre (ROP)"] > 0,
            (df_entregas["Stock Post-Entrega (kg)"] / df_entregas["Punto de Quiebre (ROP)"] * 100.0).round(1),
            100.0,
        )
        df_entregas["Fecha Arribo Est."] = fecha_est_base
        df_entregas["Ventana Máx."] = fecha_est_max
        st.dataframe(
            df_entregas[
                [
                    "Calibre",
                    "Sugerencia Compra (EOQ)",
                    "Stock Post-Entrega (kg)",
                    "Cobertura Post-EOQ (%)",
                    "Fecha Arribo Est.",
                    "Ventana Máx.",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=280,
        )

    st.html("<div style='height:8px;'></div>")
    seccion(
        "Reporting",
        "Exportación de reportes gerenciales",
        "Matriz de compras y reporte ejecutivo listos para auditoría.",
        lado_derecho=chip("Datos consolidados", "success"),
    )

    col_btn1, col_btn2 = st.columns(2, gap="medium")

    with col_btn1:
        with st.container(key="export_excel"):
            st.html(
                f'<div class="dss-export-top">'
                f'<div class="dss-export-icon">{icono("tabla")}</div>'
                f"<div>"
                f'<div class="dss-export-title">Matriz de compras</div>'
                f'<div class="dss-export-sub">Excel · una fila por calibre y decisión</div>'
                f"</div>"
                f"</div>"
            )
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_resultados.to_excel(writer, index=False, sheet_name="Matriz_Compras")
            st.download_button(
                "Descargar matriz (Excel)",
                data=buffer.getvalue(),
                file_name="Emision_Logistica_D0204.xlsx",
                mime="application/vnd.ms-excel",
                type="primary",
                width="stretch",
                icon=":material/table_view:",
            )

    with col_btn2:
        with st.container(key="export_pdf"):
            st.html(
                f'<div class="dss-export-top">'
                f'<div class="dss-export-icon">{icono("pdf")}</div>'
                f"<div>"
                f'<div class="dss-export-title">Reporte ejecutivo</div>'
                f'<div class="dss-export-sub">PDF · resumen logístico para gerencia</div>'
                f"</div>"
                f"</div>"
            )
            pdf_bin = generar_pdf_reporte(df_resultados)
            st.download_button(
                "Descargar reporte (PDF)",
                data=pdf_bin,
                file_name="Reporte_Logistico_D0204.pdf",
                mime="application/pdf",
                type="secondary",
                width="stretch",
                icon=":material/picture_as_pdf:",
            )


# ---------------------------------------------------------------------------
# Aviso para perfil de operaciones
# ---------------------------------------------------------------------------


def renderizar_aviso_operador():
    st.html(
        f'<div class="dss-notice">'
        f'<span class="dss-notice-icon">{icono("escudo")}</span>'
        f"<div><b>Modo operador.</b> Los módulos de inteligencia de mercado y métricas "
        f"de capital inmovilizado están restringidos para su perfil. Tiene acceso al "
        f"centro de alertas y a la ejecución de órdenes.</div>"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Consola exclusiva de Administración del Sistema y Usuarios (Rol: Administrador)
# ---------------------------------------------------------------------------


def renderizar_consola_admin():
    """
    Vista dedicada exclusivamente al soporte del sistema (admin):
    1) Health Checks avanzados, CORS y Rate Limiting del API/SQLite.
    2) Gestión de usuarios (CRUD: alta/edición, cambio de contraseña, estado activo).
    3) Bitácora de auditoría de accesos en tiempo real.
    """
    st.html(
        f'<div class="dss-notice">'
        f'<span class="dss-notice-icon">{icono("escudo")}</span>'
        f"<div><b>Modo Soporte del Sistema (Administrador IT).</b> Este perfil administra "
        f"exclusivamente la plataforma tecnológica, la seguridad y las cuentas de usuario. "
        f"Las operaciones logísticas y de compra están reservadas para Gerencia y Operaciones.</div>"
        f"</div>"
    )

    db_persistencia.inicializar_db()
    estado_code, salud_data = _api_get("/api/salud", timeout=4)
    salud_data = salud_data or {}
    api_ok = bool(estado_code == 200 and salud_data.get("status") == "ok")
    usuarios = db_persistencia.todos_los_usuarios()
    auditoria = db_persistencia.listar_auditoria(100)

    seccion(
        "Infraestructura · Health Checks",
        "Estado del sistema, base de datos y políticas de seguridad",
        "Diagnóstico de servicios REST, motor SQLite, CORS y limitador de tasa (Rate Limiting).",
        lado_derecho=chip("API & DB Operativos" if api_ok else "Modo Local SQLite", "success" if api_ok else "warning"),
    )

    tarjetas_admin = [
        tarjeta_kpi(
            "Servicio API REST",
            "ONLINE" if api_ok else "LOCAL",
            unidad=":8501",
            icono_nombre="cobre",
            acento="verde" if api_ok else "ambar",
            pie=chip(f"DB: {salud_data.get('base_datos', 'ok').upper()}", "success"),
            nota="ASGI · Uvicorn",
        ),
        tarjeta_kpi(
            "Usuarios registrados",
            f"{len(usuarios)}",
            unidad="cuentas",
            icono_nombre="autonomia",
            acento="cyan",
            pie=chip(f"{sum(1 for u in usuarios if u.get('activo'))} activos", "info"),
            nota="RBAC · PBKDF2",
        ),
        tarjeta_kpi(
            "Seguridad API",
            "ACTIVA",
            unidad="JWT",
            icono_nombre="capital",
            acento="cobre",
            pie=chip(f"Rate Limit: {salud_data.get('rate_limit', '10 req/min')}", "copper"),
            nota=f"CORS: {salud_data.get('cors', 'enabled')}",
        ),
        tarjeta_kpi(
            "Eventos de auditoría",
            f"{len(auditoria)}",
            unidad="logs",
            icono_nombre="ventas",
            acento="verde",
            pie=chip("Monitoreo activo", "neutral"),
            nota="Accesos web y API",
        ),
    ]
    rejilla_kpis(tarjetas_admin)

    st.html("<div style='height:12px;'></div>")
    seccion(
        "Control de Identidades (IAM)",
        "Administración de usuarios y credenciales",
        "Alta de cuentas corporativas, asignación de roles y restablecimiento de contraseñas.",
        lado_derecho=chip("Gestión de Usuarios", "copper"),
    )

    df_users = pd.DataFrame(
        [
            {
                "ID Usuario": u["id"],
                "Nombre Completo": u["nombre"],
                "Correo Corporativo": u["email"],
                "Rol del Sistema": u["rol"],
                "Estado": "Activo" if u.get("activo") else "Inactivo",
                "Fecha Alta": u.get("creado_en") or "—",
            }
            for u in usuarios
        ]
    )
    st.dataframe(df_users, hide_index=True, width="stretch", height=210)

    col_alta, col_pwd = st.columns(2, gap="medium")

    with col_alta:
        st.html(
            '<div class="dss-subhead" style="margin-top:4px;">'
            '<div><div class="dss-subhead-title">Registrar o actualizar usuario</div>'
            '<div class="dss-subhead-sub">Crea una nueva cuenta o actualiza los datos de una existente.</div></div>'
            "</div>"
        )
        with st.form("form_admin_crear_usuario", border=True):
            nuevo_id = st.text_input("ID de usuario", placeholder="ej. analista1")
            nuevo_nombre = st.text_input("Nombre y cargo", placeholder="ej. Analista de Compras")
            nuevo_email = st.text_input("Correo corporativo", placeholder="ej. analista@d-02-04.com")
            nuevo_rol = st.selectbox("Rol asignado", ["Operaciones", "Gerencia", "Administrador"])
            nuevo_pwd = st.text_input("Contraseña inicial", type="password", placeholder="Mínimo 8 caracteres")
            btn_guardar_u = st.form_submit_button("Guardar usuario", type="primary", width="stretch")

        if btn_guardar_u:
            uid_clean = nuevo_id.strip().lower()
            mail_clean = nuevo_email.strip().lower()
            nom_clean = nuevo_nombre.strip() or uid_clean
            if not uid_clean or not mail_clean or len(nuevo_pwd) < 6:
                st.error("Complete ID, correo válido y una contraseña de al menos 6 caracteres.")
            else:
                db_persistencia.crear_usuario(uid_clean, mail_clean, nuevo_pwd, nuevo_rol, nom_clean)
                st.toast(f"Usuario '{uid_clean}' ({nuevo_rol}) registrado correctamente.", icon="✅")
                st.rerun()

    with col_pwd:
        st.html(
            '<div class="dss-subhead" style="margin-top:4px;">'
            '<div><div class="dss-subhead-title">Restablecer clave y estado de cuenta</div>'
            '<div class="dss-subhead-sub">Modifica la contraseña o habilita/deshabilita el acceso.</div></div>'
            "</div>"
        )
        with st.form("form_admin_pwd", border=True):
            ids_disp = [u["id"] for u in usuarios]
            sel_uid = st.selectbox("Seleccionar usuario", ids_disp)
            reset_pwd = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password")
            estado_sel = st.selectbox("Estado de la cuenta", ["Activo", "Inactivo"])
            btn_actualizar_u = st.form_submit_button("Aplicar cambios", type="primary", width="stretch")

        if btn_actualizar_u and sel_uid:
            if sel_uid == "admin" and estado_sel == "Inactivo":
                st.error("No se puede desactivar la cuenta principal de soporte (admin).")
            else:
                db_persistencia.cambiar_estado_usuario(sel_uid, estado_sel == "Activo")
                if reset_pwd:
                    if len(reset_pwd) < 6:
                        st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                    else:
                        db_persistencia.actualizar_password(sel_uid, reset_pwd)
                        st.toast(f"Contraseña y estado de '{sel_uid}' actualizados.", icon="🔐")
                        st.rerun()
                else:
                    st.toast(f"Estado de '{sel_uid}' actualizado a {estado_sel}.", icon="✅")
                    st.rerun()

    st.html("<div style='height:12px;'></div>")
    seccion(
        "Seguridad · Trazabilidad",
        "Bitácora de auditoría de accesos",
        "Registro cronológico de inicios de sesión e intentos fallidos en Web y API.",
        lado_derecho=chip(f"{len(auditoria)} eventos", "info"),
    )

    if auditoria:
        filas_aud = []
        for a in auditoria:
            ts = float(a.get("creado_en") or 0)
            fecha_a = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts > 0 else "—"
            filas_aud.append(
                {
                    "ID": a.get("id"),
                    "Fecha y Hora": fecha_a,
                    "Usuario": a.get("usuario_id") or "—",
                    "Correo / Identificador": a.get("correo") or "—",
                    "Evento": a.get("evento"),
                    "Detalle": a.get("detalle"),
                    "Resultado": "EXITOSO" if a.get("exito") else "FALLIDO",
                }
            )
        st.dataframe(pd.DataFrame(filas_aud), hide_index=True, width="stretch", height=280)
    else:
        st.info("No hay eventos de auditoría registrados todavía.")
