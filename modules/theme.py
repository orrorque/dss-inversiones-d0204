"""
Sistema de diseño del DSS (Inversiones D-02-04).

Capa 100 % visual: tokens de color, CSS global, componentes HTML y
estilización de figuras Plotly. No contiene cálculos de negocio.
"""

from __future__ import annotations

import base64
import math
import os

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Tokens de diseño
# ---------------------------------------------------------------------------

PALETA = {
    "fondo": "#0A0F1A",
    "fondo_2": "#0C1322",
    "superficie": "#111A2B",
    "superficie_2": "#0E1727",
    "borde": "rgba(148,163,184,.13)",
    "borde_fuerte": "rgba(148,163,184,.24)",
    "texto": "#E8EEF7",
    "texto_2": "#C3CFE0",
    "muted": "#8FA0B8",
    "faint": "#64748B",
    "cobre": "#F2B45C",
    "cobre_2": "#E08C34",
    "cyan": "#4CC9F0",
    "verde": "#3DDC97",
    "ambar": "#F7C948",
    "rojo": "#FF6B6B",
    "violeta": "#A78BFA",
}

ACENTOS = {
    "cobre": ("#F2B45C", "rgba(242,180,92,.12)", "rgba(242,180,92,.32)", "rgba(242,180,92,.18)"),
    "cyan": ("#4CC9F0", "rgba(76,201,240,.12)", "rgba(76,201,240,.30)", "rgba(76,201,240,.18)"),
    "verde": ("#3DDC97", "rgba(61,220,151,.12)", "rgba(61,220,151,.30)", "rgba(61,220,151,.18)"),
    "rojo": ("#FF6B6B", "rgba(255,107,107,.12)", "rgba(255,107,107,.30)", "rgba(255,107,107,.18)"),
    "violeta": ("#A78BFA", "rgba(167,139,250,.12)", "rgba(167,139,250,.30)", "rgba(167,139,250,.18)"),
}

MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# ---------------------------------------------------------------------------
# Iconografía (SVG inline, sin dependencias externas)
# ---------------------------------------------------------------------------

ICONOS = {
    "capital": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="6" width="19" height="12" '
        'rx="2.5"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5h.01M18 14.5h.01"/></svg>'
    ),
    "autonomia": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
        '<path d="M12 7v5l3.2 2"/></svg>'
    ),
    "cobre": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M3 17.5 9 11l4 4 8-8.5"/>'
        '<path d="M15 6.5h6v6"/></svg>'
    ),
    "ventas": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.8 21 7.4v9.2L12 21.2 3 16.6V7.4z"/>'
        '<path d="m3 7.4 9 4.7 9-4.7M12 12.1v9.1"/></svg>'
    ),
    "alerta": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>'
        '<path d="M12 9v4M12 17h.01"/></svg>'
    ),
    "check": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
        '<path d="m8.2 12.3 2.5 2.5 5.1-5.4"/></svg>'
    ),
    "escudo": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.8 20 6v6c0 5-3.4 7.9-8 9.2-4.6-1.3-8-4.2-8-9.2V6Z"/>'
        '<path d="m8.7 12 2.2 2.2 4.4-4.6"/></svg>'
    ),
    "tabla": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/>'
        '<path d="M3 9.5h18M9.5 9.5V20"/></svg>'
    ),
    "pdf": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M14 2.8H6.5A2.5 2.5 0 0 0 4 5.3v13.4a2.5 2.5 0 0 0 2.5 2.5h11a2.5 2.5 0 0 0 2.5-2.5V8.3Z"/>'
        '<path d="M14 2.8v5.5h6M8 13h8M8 17h5"/></svg>'
    ),
    "candado": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10.5" width="16" height="10.5" rx="2.5"/>'
        '<path d="M8 10.5V7.7a4 4 0 0 1 8 0v2.8"/></svg>'
    ),
    "info": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
        '<path d="M12 11v5M12 7.8h.01"/></svg>'
    ),
}

# ---------------------------------------------------------------------------
# Plotly
# ---------------------------------------------------------------------------

PLOTLY_CONFIG = {
    "displaylogo": False,
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}

_PLANTILLA_DSS = go.layout.Template(
    layout=go.Layout(
        colorway=[
            PALETA["cyan"],
            PALETA["cobre"],
            PALETA["verde"],
            PALETA["rojo"],
            PALETA["violeta"],
            PALETA["ambar"],
        ],
        font=dict(
            family="Inter, 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
            color=PALETA["texto_2"],
            size=12,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="#0B1424",
            bordercolor="rgba(148,163,184,.30)",
            font=dict(
                family="Inter, 'Segoe UI', sans-serif",
                color=PALETA["texto"],
                size=12,
            ),
            align="left",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(color=PALETA["muted"], size=11),
        ),
        margin=dict(l=8, r=14, t=26, b=8),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="rgba(148,163,184,.14)",
            linewidth=1,
            ticks="",
            tickfont=dict(color="#7C8DA6", size=11),
            automargin=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148,163,184,.075)",
            gridwidth=1,
            zeroline=False,
            showline=False,
            ticks="",
            tickfont=dict(color="#7C8DA6", size=11),
            automargin=True,
        ),
    )
)

pio.templates["dss"] = _PLANTILLA_DSS
pio.templates.default = "dss"


def estilizar_figura(
    fig: go.Figure,
    *,
    alto: int = 300,
    leyenda: bool = True,
    hovermode: str = "x unified",
    fecha: bool = False,
    moneda: bool = False,
    ticksuffix: str | None = None,
    tickangle: int | None = None,
    margen: dict | None = None,
) -> go.Figure:
    """Aplica la capa visual corporativa a una figura existente."""

    fig.update_layout(
        template="dss",
        height=alto,
        showlegend=leyenda,
        hovermode=hovermode,
        bargap=0.38,
        # Streamlit inyecta su propio fondo/tipografía si el layout raíz no los
        # declara; los fijamos explícitamente para conservar la identidad visual.
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Inter, 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
            color=PALETA["texto_2"],
            size=12,
        ),
    )
    if margen:
        fig.update_layout(margin=margen)
    if leyenda:
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                font=dict(color=PALETA["muted"], size=11),
            )
        )
    if fecha:
        fig.update_xaxes(tickformat="%b %y", hoverformat="%b %Y")
    if moneda:
        fig.update_yaxes(tickprefix="$", separatethousands=True)
    if ticksuffix:
        fig.update_yaxes(ticksuffix=ticksuffix)
    if tickangle is not None:
        fig.update_xaxes(tickangle=tickangle)
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="#0B1424",
            bordercolor="rgba(148,163,184,.30)",
            font=dict(
                family="Inter, 'Segoe UI', sans-serif",
                color=PALETA["texto"],
                size=12,
            ),
            align="left",
        )
    )
    return fig


# ---------------------------------------------------------------------------
# Helpers de componentes
# ---------------------------------------------------------------------------


def _acentos(acento: str) -> str:
    color, bg, borde, suave = ACENTOS.get(acento, ACENTOS["cobre"])
    return (
        f"--accent:{color};--accent-bg:{bg};--accent-bd:{borde};"
        f"--accent-soft:{suave};--accent-2:{color};"
    )


def _uri_svg(svg: str) -> str:
    """Convierte un SVG en data URI; st.html elimina el SVG inline al sanitizar."""
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


_MAPA_ASSETS = {
    "circular": ["assets/circular.png", "assets/circular.jpg", "assets/circular.jpeg"],
    "rectangular": [
        "assets/rectangular.png",
        "assets/rectagunlar.png",
        "assets/rectangular.jpg",
        "assets/rectagunlar.jpg",
    ],
    "cuadrado": ["assets/cuadrado.png", "assets/cuadrado.jpg", "assets/cuadrado.jpeg"],
}


def ruta_asset(nombre: str) -> str | None:
    """Devuelve la ruta existente para 'circular', 'rectangular' o 'cuadrado'."""
    for ruta in _MAPA_ASSETS.get(nombre, [f"assets/{nombre}.png"]):
        if os.path.exists(ruta):
            return ruta
    return None


@st.cache_data(show_spinner=False)
def obtener_imagen_b64(nombre: str) -> str:
    """Devuelve un data URI base64 listo para incrustar en componentes HTML."""
    ruta = ruta_asset(nombre)
    if not ruta:
        return ""
    mime = "image/png" if ruta.lower().endswith(".png") else "image/jpeg"
    with open(ruta, "rb") as archivo:
        codificado = base64.b64encode(archivo.read()).decode("ascii")
    return f"data:{mime};base64,{codificado}"


def icono(nombre: str) -> str:
    """Icono monocromo: máscara CSS que hereda el color de la clase contenedora."""
    svg = ICONOS.get(nombre, ICONOS["info"])
    return f"<span class=\"dss-ico\" style=\"--ico:url('{_uri_svg(svg)}')\" aria-hidden=\"true\"></span>"


def chip(texto: str, variante: str = "neutral") -> str:
    return f'<span class="dss-chip dss-chip--{variante}">{texto}</span>'


def sparkline(
    valores,
    color: str,
    *,
    uid: str = "spark",
    ancho: int = 120,
    alto: int = 38,
) -> str:
    """Genera un sparkline SVG puramente decorativo a partir de una serie."""

    limpios = []
    for valor in valores:
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numero):
            limpios.append(numero)

    if len(limpios) < 2:
        return ""

    minimo, maximo = min(limpios), max(limpios)
    rango = (maximo - minimo) or 1.0
    paso = ancho / (len(limpios) - 1)

    puntos = []
    for i, valor in enumerate(limpios):
        x = i * paso
        y = (alto - 5) - ((valor - minimo) / rango) * (alto - 10)
        puntos.append((x, y))

    linea = " ".join(f"{x:.2f},{y:.2f}" for x, y in puntos)
    area = (
        f"M{puntos[0][0]:.2f},{alto:.2f} "
        + " ".join(f"L{x:.2f},{y:.2f}" for x, y in puntos)
        + f" L{puntos[-1][0]:.2f},{alto:.2f} Z"
    )
    last_x, last_y = puntos[-1]
    gid = f"dssGrad-{uid}".replace(" ", "")

    svg = (
        f'<svg viewBox="0 0 {ancho} {alto}" preserveAspectRatio="none">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity=".32"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        f'<path d="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{linea}" fill="none" stroke="{color}" stroke-width="1.9" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="2.4" fill="{color}"/>'
        f"</svg>"
    )
    return f'<img class="dss-spark" alt="" aria-hidden="true" src="{_uri_svg(svg)}">'


def seccion(
    etiqueta: str,
    titulo: str,
    subtitulo: str = "",
    *,
    lado_derecho: str = "",
) -> None:
    """Cabecera de sección consistente para todo el tablero."""

    sub = f'<div class="dss-section-sub">{subtitulo}</div>' if subtitulo else ""
    lado = f'<div class="dss-section-side">{lado_derecho}</div>' if lado_derecho else ""
    st.html(
        f'<div class="dss-section">'
        f'<div class="dss-section-copy">'
        f'<div class="dss-eyebrow">{etiqueta}</div>'
        f'<div class="dss-section-title">{titulo}</div>'
        f"{sub}"
        f"</div>"
        f"{lado}"
        f"</div>"
    )


def tarjeta_kpi(
    etiqueta: str,
    valor: str,
    *,
    decimales: str = "",
    unidad: str = "",
    icono_nombre: str = "capital",
    acento: str = "cobre",
    pie: str = "",
    nota: str = "",
    spark: str = "",
    medidor: float | None = None,
    color_medidor: str = "",
) -> str:
    """Construye el HTML de una KPI card unificada sin bordes divisorios."""

    decimales_html = f'<span class="dss-kpi-dec">{decimales}</span>' if decimales else ""
    unidad_html = f'<span class="dss-kpi-unit">{unidad}</span>' if unidad else ""
    pie_html = f'<div class="dss-kpi-pie">{pie}</div>' if pie else ""
    nota_html = f'<span class="dss-kpi-note">{nota}</span>' if nota else ""

    return (
        f'<div class="dss-kpi" style="{_acentos(acento)}">'
        f'<div class="dss-kpi-head">'
        f'<span class="dss-kpi-icon">{icono(icono_nombre)}</span>'
        f'<span class="dss-kpi-label">{etiqueta}</span>'
        f"</div>"
        f'<div class="dss-kpi-value">{valor}{decimales_html}{unidad_html}</div>'
        f"{spark}"
        f'<div class="dss-kpi-foot">{pie_html}{nota_html}</div>'
        f"</div>"
    )


def rejilla_kpis(tarjetas: list[str]) -> None:
    st.html(f'<div class="dss-kpi-grid">{"".join(tarjetas)}</div>')


# ---------------------------------------------------------------------------
# CSS global
# ---------------------------------------------------------------------------

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root{
  --dss-bg:#0A0F1A;
  --dss-surface:#111A2B;
  --dss-border:rgba(148,163,184,.13);
  --dss-border-strong:rgba(148,163,184,.24);
  --dss-text:#E8EEF7;
  --dss-text-2:#C3CFE0;
  --dss-muted:#8FA0B8;
  --dss-faint:#64748B;
  --dss-copper:#F2B45C;
  --dss-green:#3DDC97;
  --dss-amber:#F7C948;
  --dss-red:#FF6B6B;
  --dss-radius:16px;
  --dss-shadow:0 18px 38px -26px rgba(0,0,0,.85);
}

html, body, [data-testid="stAppViewContainer"], button, input, textarea, select,
[data-testid="stMarkdownContainer"]{
  font-family:'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
  font-feature-settings:'cv02','cv03','cv04','ss01';
}

[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1100px 560px at 10% -12%, rgba(242,180,92,.10), transparent 62%),
    radial-gradient(900px 480px at 102% -2%, rgba(76,201,240,.075), transparent 58%),
    linear-gradient(180deg,#0A0F1A 0%,#090E18 100%);
  background-attachment:fixed;
}
[data-testid="stApp"]{ background:transparent; }
[data-testid="stHeader"]{ background:transparent; height:2.4rem; }
[data-testid="stAppDeployButton"]{ display:none !important; }
[data-testid="stMainMenu"]{ opacity:.55; transition:opacity .2s ease; }
[data-testid="stMainMenu"]:hover{ opacity:1; }

[data-testid="stMainBlockContainer"], .block-container{
  padding:1.1rem 2.4rem 3.5rem !important;
  max-width:1560px;
}

h1,h2,h3,h4,h5,h6{ color:#F4F8FE; letter-spacing:-.02em; font-weight:700; }
[data-testid="stMarkdownContainer"] p{ color:var(--dss-text-2); line-height:1.62; }
[data-testid="stCaptionContainer"] p{ color:var(--dss-muted); }

::-webkit-scrollbar{ width:8px; height:8px; }
::-webkit-scrollbar-track{ background:transparent; }
::-webkit-scrollbar-thumb{ background:rgba(148,163,184,.22); border-radius:99px; }
::-webkit-scrollbar-thumb:hover{ background:rgba(148,163,184,.34); }

/* ---------------- Sidebar ---------------- */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0B1322 0%,#080D17 100%);
  border-right:1px solid var(--dss-border);
}
[data-testid="stSidebarContent"]{ padding-top:.35rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:.55rem; }
[data-testid="stSidebar"] hr{ margin:.4rem 0; border-color:var(--dss-border); }
/* Contenedor del logotipo: escala fluida al ancho de la barra lateral sin distorsión */
.dss-sidebar-logo-wrap{
  width:100%; padding:6px 4px 2px;
  display:flex; justify-content:center; align-items:center;
}
.dss-sidebar-logo{
  width:100%; max-width:100%; height:auto;
  max-height:132px; object-fit:contain; display:block;
  filter:drop-shadow(0 8px 18px rgba(0,0,0,.45));
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] label p,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label p{
  font-size:.7rem; text-transform:uppercase; letter-spacing:.12em;
  color:var(--dss-muted); font-weight:600;
}
.dss-side-caption{
  margin-top:10px; text-align:center; font-size:.63rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--dss-faint); font-weight:600;
}
.dss-side-label{
  font-size:.63rem; letter-spacing:.18em; text-transform:uppercase;
  color:var(--dss-faint); font-weight:700; margin:14px 0 2px;
}
[class*="st-key-sidebar_brand"],
[class*="st-key-sidebar_profile"]{
  background:var(--dss-surface);
  border:1px solid var(--dss-border);
  border-radius:14px;
  padding:12px 13px;
  box-shadow:var(--dss-shadow);
}
.dss-profile{ display:flex; align-items:center; gap:11px; }
.dss-avatar{
  width:38px; height:38px; border-radius:11px; flex:0 0 38px;
  display:grid; place-items:center; font-weight:700; font-size:.82rem;
  color:#241505; background:linear-gradient(135deg,#F7CC86,#E5953F);
  box-shadow:0 8px 18px -10px rgba(242,180,92,.75);
}
.dss-profile-name{ font-size:.84rem; font-weight:650; color:#F4F8FE; line-height:1.2; }
.dss-profile-role{ font-size:.66rem; color:var(--dss-muted); margin-top:2px; }
.dss-profile-role b{ color:#F7D9A8; font-weight:600; }
.dss-side-footer{
  margin-top:12px; padding-top:8px;
  font-size:.64rem; color:var(--dss-faint); line-height:1.6;
}
.dss-side-status{ display:flex; align-items:center; gap:7px; color:var(--dss-text-2); font-weight:600; }
.dss-side-status .dss-dot-live{ width:6px; height:6px; }

/* ---------------- Inputs / widgets ---------------- */
[data-testid="stWidgetLabel"] p{
  font-size:.7rem; text-transform:uppercase; letter-spacing:.11em;
  color:var(--dss-muted); font-weight:600;
}
[data-testid="stTextInputRootElement"]{
  background:rgba(8,14,26,.82);
  border:1px solid var(--dss-border);
  border-radius:11px;
  transition:border-color .18s ease, box-shadow .18s ease;
}
[data-testid="stTextInputRootElement"]:focus-within{
  border-color:rgba(242,180,92,.55);
  box-shadow:0 0 0 3px rgba(242,180,92,.10);
}
[data-testid="stTextInputRootElement"] input{ color:var(--dss-text); }
[data-baseweb="select"] > div{
  background:rgba(8,14,26,.82) !important;
  border:1px solid var(--dss-border) !important;
  border-radius:11px !important;
  color:var(--dss-text) !important;
  transition:border-color .18s ease;
}
[data-baseweb="select"] > div:hover{ border-color:var(--dss-border-strong) !important; }
[data-baseweb="popover"] [role="listbox"]{
  background:#0F1A2D !important;
  border:1px solid var(--dss-border-strong) !important;
  border-radius:12px !important;
}
[data-baseweb="popover"] [role="option"]{ color:var(--dss-text-2) !important; }
[data-baseweb="popover"] [role="option"]:hover{ background:rgba(242,180,92,.10) !important; }

/* ---------------- Botones ---------------- */
.stButton > button,
[data-testid="stDownloadButton"] button,
[data-testid="stFormSubmitButton"] button{
  border-radius:10px;
  font-weight:600;
  font-size:.83rem;
  letter-spacing:.01em;
  border:1px solid var(--dss-border-strong);
  background:rgba(23,35,55,.72);
  color:var(--dss-text);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
  transition:transform .16s ease, border-color .16s ease, box-shadow .16s ease, filter .16s ease;
}
.stButton > button:hover,
[data-testid="stDownloadButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover{
  border-color:rgba(242,180,92,.48);
  color:#FFFFFF;
  transform:translateY(-1px);
  box-shadow:0 12px 26px -18px rgba(242,180,92,.55);
}
.stButton > button:active{ transform:translateY(0); }
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"]{
  background:linear-gradient(135deg,#F7CC86 0%,#E5953F 100%);
  color:#241505;
  border:1px solid rgba(255,214,153,.65);
  box-shadow:0 12px 26px -14px rgba(242,180,92,.75);
}
.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover{
  color:#1B0F02;
  filter:brightness(1.05);
  box-shadow:0 16px 32px -14px rgba(242,180,92,.85);
}
[data-testid="InputInstructions"]{
  display:none !important;
  visibility:hidden !important;
  height:0 !important;
  overflow:hidden !important;
}

/* ---------------- Contenedores / tarjetas ---------------- */
/* ---------------- Contenedores / tarjetas unificadas ---------------- */
[class*="st-key-card_"]{
  background:var(--dss-surface);
  border:1px solid var(--dss-border);
  border-radius:var(--dss-radius);
  padding:18px 20px 14px;
  box-shadow:var(--dss-shadow);
}
[class*="st-key-card_"] [data-testid="stPlotlyChart"]{ margin-top:2px; }
[data-testid="stPlotlyChart"]{ border-radius:10px; overflow:hidden; }

[data-testid="stAlertContainer"]{
  border-radius:12px;
  border:1px solid var(--dss-border);
  background:var(--dss-surface);
}
[data-testid="stExpander"]{
  background:var(--dss-surface);
  border:1px solid var(--dss-border);
  border-radius:14px;
  overflow:hidden;
}
[data-testid="stExpander"] summary{ font-weight:600; color:var(--dss-text-2); }
[data-testid="stDataFrame"]{
  border:1px solid var(--dss-border);
  border-radius:12px;
  overflow:hidden;
}

/* ---------------- Topbar con circular + rectangular ---------------- */
.dss-topbar{
  display:flex; justify-content:space-between; align-items:center; gap:20px;
  padding:16px 22px; margin:0 0 20px;
  border:1px solid var(--dss-border); border-radius:16px;
  background:var(--dss-surface);
  box-shadow:var(--dss-shadow);
  position:relative; overflow:hidden;
}
.dss-topbar-id{ display:flex; gap:16px; align-items:center; z-index:1; }
.dss-topbar-crest{
  width:64px; height:64px; flex:0 0 64px; border-radius:50%;
  object-fit:contain; padding:3px;
  background:#0D1524; border:1px solid var(--dss-border);
}
.dss-topbar-banner{
  height:54px; width:auto; max-width:170px; object-fit:contain;
  border-radius:10px; padding:4px 8px;
  background:#0D1524; border:1px solid var(--dss-border);
}
.dss-logo-badge{
  width:46px; height:46px; border-radius:13px; display:grid; place-items:center;
  background:rgba(242,180,92,.12);
  border:1px solid rgba(242,180,92,.28); color:var(--dss-copper);
}
.dss-logo-badge .dss-ico{ width:24px; height:24px; }
.dss-topbar-eyebrow{
  font-size:.64rem; letter-spacing:.22em; text-transform:uppercase;
  color:var(--dss-copper); font-weight:700;
}
.dss-topbar-title{
  font-size:1.38rem; font-weight:750; color:#F7FAFF;
  letter-spacing:-.03em; line-height:1.15; margin-top:2px;
}
.dss-topbar-sub{ font-size:.77rem; color:var(--dss-muted); margin-top:3px; }
.dss-topbar-meta{ display:flex; gap:18px; align-items:center; z-index:1; flex-wrap:wrap; }
.dss-meta-item{ display:flex; flex-direction:column; gap:3px; }
.dss-meta-item span{
  font-size:.6rem; letter-spacing:.15em; text-transform:uppercase;
  color:var(--dss-faint); font-weight:600;
}
.dss-meta-item b{ font-size:.82rem; color:var(--dss-text); font-weight:600; }
.dss-live{
  display:inline-flex; align-items:center; gap:8px; padding:7px 12px;
  border-radius:999px; background:rgba(61,220,151,.08);
  border:1px solid rgba(61,220,151,.30); color:#9BEFC8;
  font-size:.72rem; font-weight:600; white-space:nowrap;
}
.dss-dot-live{
  width:7px; height:7px; border-radius:50%; background:var(--dss-green);
  box-shadow:0 0 0 3px rgba(61,220,151,.12);
  animation:dssPulse 2.4s infinite;
}
@keyframes dssPulse{
  0%,100%{ box-shadow:0 0 0 3px rgba(61,220,151,.12); }
  50%{ box-shadow:0 0 0 7px rgba(61,220,151,.03); }
}

/* ---------------- Secciones ---------------- */
.dss-section{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin:10px 0 14px; }
.dss-section-copy{ display:flex; flex-direction:column; gap:2px; }
.dss-eyebrow{
  font-size:.62rem; letter-spacing:.2em; text-transform:uppercase;
  color:var(--dss-copper); font-weight:700;
}
.dss-section-title{ font-size:1.04rem; font-weight:700; color:#F2F7FE; letter-spacing:-.01em; }
.dss-section-sub{ font-size:.77rem; color:var(--dss-muted); }
.dss-section-side{ margin-bottom:4px; }

/* ---------------- KPI (rectángulos limpios y unificados) ---------------- */
.dss-kpi-grid{
  display:grid; grid-template-columns:repeat(4,minmax(0,1fr));
  gap:14px; margin-bottom:6px;
}
.dss-kpi{
  position:relative; overflow:hidden; min-height:148px;
  display:flex; flex-direction:column;
  padding:18px 20px 16px; border-radius:16px;
  border:1px solid var(--dss-border);
  background:var(--dss-surface);
  box-shadow:var(--dss-shadow);
  transition:border-color .18s ease, transform .18s ease;
}
.dss-kpi:hover{ border-color:var(--dss-border-strong); transform:translateY(-2px); }
.dss-kpi-head{ display:flex; align-items:center; gap:9px; margin-bottom:13px; position:relative; z-index:1; }
.dss-kpi-icon{
  width:30px; height:30px; border-radius:9px; flex:0 0 30px;
  display:grid; place-items:center; color:var(--accent);
  background:var(--accent-bg); border:1px solid var(--accent-bd);
}
.dss-kpi-icon .dss-ico{ width:16px; height:16px; }
.dss-kpi-label{
  font-size:.69rem; text-transform:uppercase; letter-spacing:.12em;
  color:var(--dss-muted); font-weight:600; line-height:1.25;
}
.dss-kpi-value{
  font-size:1.82rem; font-weight:750; color:#F7FAFF; letter-spacing:-.035em;
  line-height:1; font-variant-numeric:tabular-nums;
  display:flex; align-items:baseline; gap:2px; position:relative; z-index:1;
}
.dss-kpi-dec{ font-size:1rem; color:var(--dss-muted); font-weight:600; letter-spacing:-.01em; }
.dss-kpi-unit{
  font-size:.73rem; color:var(--dss-muted); font-weight:600;
  margin-left:7px; letter-spacing:0;
}
.dss-kpi-foot{
  margin-top:auto; padding-top:12px; display:flex; align-items:center;
  justify-content:space-between; gap:6px 8px; position:relative; z-index:1;
  flex-wrap:wrap;
}
.dss-kpi-pie{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.dss-kpi-note{ font-size:.68rem; color:var(--dss-faint); font-weight:500; white-space:nowrap; }
.dss-spark{
  position:absolute; right:14px; bottom:44px; width:92px; height:32px;
  opacity:.9; pointer-events:none;
}

/* ---------------- Chips ---------------- */
.dss-chip{
  display:inline-flex; align-items:center; gap:6px; border-radius:999px;
  padding:4px 10px; font-size:.67rem; font-weight:650; letter-spacing:.02em;
  white-space:nowrap; border:1px solid transparent;
}
.dss-chip--neutral{ background:rgba(148,163,184,.09); border-color:rgba(148,163,184,.18); color:var(--dss-text-2); }
.dss-chip--danger{ background:rgba(255,107,107,.10); border-color:rgba(255,107,107,.30); color:#FFB3B3; }
.dss-chip--warning{ background:rgba(247,201,72,.10); border-color:rgba(247,201,72,.30); color:#FFE29A; }
.dss-chip--success{ background:rgba(61,220,151,.10); border-color:rgba(61,220,151,.30); color:#9BEFC8; }
.dss-chip--info{ background:rgba(76,201,240,.10); border-color:rgba(76,201,240,.30); color:#A9E6FB; }
.dss-chip--copper{ background:rgba(242,180,92,.10); border-color:rgba(242,180,92,.30); color:#F7D9A8; }

/* ---------------- Alertas (tipografía roja de alta visibilidad) ---------------- */
.dss-alert,
.dss-alert--critical,
.dss-alert--warn,
.dss-alert--ok{
  position:relative; overflow:hidden; border-radius:16px;
  padding:18px 20px 15px; margin:4px 0 22px;
  border:1px solid var(--dss-border);
  background:var(--dss-surface);
  box-shadow:var(--dss-shadow);
}
.dss-alert-head{
  display:flex; justify-content:space-between; gap:18px; flex-wrap:wrap;
  align-items:flex-start; position:relative; z-index:1;
}
.dss-alert-heading{ display:flex; gap:13px; align-items:center; }
.dss-alert-kicker{
  font-size:.63rem; text-transform:uppercase; letter-spacing:.2em;
  color:#FF5252 !important; font-weight:800;
}
.dss-alert-title{
  font-size:1.05rem; font-weight:800; color:#FF4D4D !important;
  letter-spacing:-.01em; margin-top:2px; line-height:1.3;
}
.dss-alert-side{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.dss-alert-time{ font-size:.69rem; color:#FF8585; font-weight:600; }
.dss-alert-copy{
  position:relative; z-index:1; font-size:.82rem; color:#FF8080 !important;
  margin:9px 0 14px; max-width:980px; line-height:1.55; font-weight:500;
}
.dss-alert-copy b{ color:#FF4242 !important; font-weight:700; }
/* Ticker: el contenido se duplica y la pista se desplaza -50 % para un bucle continuo */
.dss-ticker{
  position:relative; z-index:1; overflow:hidden; padding:4px 0 8px;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent);
          mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent);
}
.dss-ticker-track{
  display:flex; width:max-content;
  animation:dssTicker var(--dss-ticker-dur,24s) linear infinite;
  animation-play-state:running !important;
  will-change:transform;
}
.dss-ticker-group{ display:flex; gap:10px; padding-right:10px; }
@keyframes dssTicker{
  from{ transform:translate3d(0,0,0); }
  to{ transform:translate3d(-50%,0,0); }
}
.dss-stock-card,
.dss-stock-card--warn{
  min-width:188px; flex:1 0 188px; border-radius:12px; padding:12px 14px;
  background:#0D1524; border:1px solid var(--dss-border);
  scroll-snap-align:start;
}
.dss-stock-top{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px; }
.dss-stock-name{ font-size:.86rem; font-weight:800; color:#FF5252; letter-spacing:-.01em; }
.dss-stock-badge{
  font-size:.58rem; text-transform:uppercase; letter-spacing:.1em;
  font-weight:700; color:#FF5252; background:rgba(255,82,82,.14);
  border-radius:5px; padding:2px 6px;
}
.dss-stock-card--warn .dss-stock-badge{ color:#FF6B6B; background:rgba(255,107,107,.12); }
.dss-stock-row{
  display:flex; justify-content:space-between; font-size:.71rem;
  color:#FF9E9E; margin:3px 0;
}
.dss-stock-row b{ color:#FF6B6B; font-weight:700; font-variant-numeric:tabular-nums; }
.dss-stock-deficit{
  font-size:.7rem; color:#FF4D4D; font-weight:700;
  display:flex; justify-content:space-between; gap:8px; margin-top:6px;
}
.dss-stock-card--warn .dss-stock-deficit{ color:#FF6B6B; }
.dss-stock-deficit b{ color:#FF3B3B; font-variant-numeric:tabular-nums; font-weight:800; }
.dss-ok-wrap{ display:flex; align-items:center; gap:14px; position:relative; z-index:1; }
.dss-ok-icon{
  width:42px; height:42px; border-radius:12px; flex:0 0 42px;
  display:grid; place-items:center; color:var(--dss-green);
  background:rgba(61,220,151,.10); border:1px solid rgba(61,220,151,.28);
}
.dss-ok-icon .dss-ico{ width:22px; height:22px; }
.dss-ok-title{ font-size:.95rem; font-weight:700; color:#E9FFF5; letter-spacing:-.01em; }
.dss-ok-sub{ font-size:.76rem; color:#A9C4B8; margin-top:2px; }
.dss-ok-side{ margin-left:auto; }

/* ---------------- Tarjetas de gráfica ---------------- */
.dss-card-head{
  display:flex; justify-content:space-between; align-items:flex-start;
  gap:12px; margin-bottom:4px;
}
.dss-card-eyebrow{
  font-size:.58rem; text-transform:uppercase; letter-spacing:.18em;
  color:var(--dss-faint); font-weight:700;
}
.dss-card-title{ font-size:.92rem; font-weight:650; color:#EEF4FC; margin-top:2px; letter-spacing:-.01em; }
.dss-card-sub{ font-size:.72rem; color:var(--dss-muted); margin-top:2px; }
.dss-stat-strip{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(94px,1fr));
  gap:8px; margin-top:8px; padding-top:8px;
}
.dss-stat{ display:flex; flex-direction:column; gap:2px; }
.dss-stat span{
  font-size:.58rem; text-transform:uppercase; letter-spacing:.1em;
  color:var(--dss-faint); font-weight:600;
}
.dss-stat b{ font-size:.79rem; color:var(--dss-text); font-weight:600; font-variant-numeric:tabular-nums; }
.dss-stat b.up{ color:#7DEBBF; }
.dss-stat b.down{ color:#FF9B9B; }

/* ---------------- Matriz de activos ---------------- */
.dss-subhead{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin:22px 0 12px; }
.dss-subhead-title{ font-size:.9rem; font-weight:700; color:#EEF4FC; letter-spacing:-.01em; }
.dss-subhead-sub{ font-size:.74rem; color:var(--dss-muted); margin-top:2px; }
/* ---------------- Mesa de Órdenes Sugeridas (Grid y Paleta Estética) ---------------- */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-asset_"]){
  display:grid !important;
  grid-template-columns:repeat(3, minmax(0, 1fr)) !important;
  gap:16px !important;
  align-items:stretch !important;
  width:100% !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-asset_"]) > [data-testid="stColumn"]{
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  flex:unset !important;
}
[class*="st-key-asset_"] [data-testid="stHorizontalBlock"]{
  display:grid !important;
  grid-template-columns:1.25fr 1fr !important;
  gap:8px !important;
  align-items:center !important;
  width:100% !important;
}
[class*="st-key-asset_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  flex:unset !important;
}

[class*="st-key-asset_"]{
  position:relative; height:100%; overflow:hidden;
  background:linear-gradient(155deg, #17263C 0%, #111C2D 100%) !important;
  border:1px solid rgba(110, 168, 245, .28) !important;
  border-radius:16px !important; padding:16px 16px 14px !important;
  margin-bottom:4px !important;
  box-shadow:0 18px 34px -22px rgba(6, 15, 32, .85) !important;
  transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
[class*="st-key-asset_"]::before{
  content:""; position:absolute; top:0; left:0; right:0; height:3px;
  background:linear-gradient(90deg, #38BDF8 0%, #818CF8 50%, #34D399 100%);
  opacity:.9;
}
[class*="st-key-asset_"]:hover{
  transform:translateY(-3px);
  border-color:rgba(56, 189, 248, .58) !important;
  box-shadow:0 24px 42px -24px rgba(14, 165, 233, .32) !important;
}
[class*="st-key-asset_"] [data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
  color:#FFFFFF !important;
  border:1px solid rgba(52, 211, 153, .45) !important;
  font-weight:700 !important;
  font-size:.76rem !important;
  box-shadow:0 10px 22px -12px rgba(16, 185, 129, .65) !important;
}
[class*="st-key-asset_"] [data-testid="stBaseButton-primary"]:hover{
  background:linear-gradient(135deg, #34D399 0%, #10B981 100%) !important;
  border-color:rgba(110, 231, 183, .75) !important;
}
[class*="st-key-asset_"] [data-testid="stBaseButton-secondary"]{
  background:rgba(244, 63, 94, .13) !important;
  color:#FDA4AF !important;
  border:1px solid rgba(244, 63, 94, .34) !important;
  font-weight:650 !important;
  font-size:.75rem !important;
}
[class*="st-key-asset_"] [data-testid="stBaseButton-secondary"]:hover{
  background:rgba(244, 63, 94, .24) !important;
  color:#FFE4E6 !important;
  border-color:rgba(251, 113, 133, .6) !important;
}

.dss-oms-summary{
  display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px;
  margin:8px 0 16px;
}
@media (max-width:980px){ .dss-oms-summary{ grid-template-columns:repeat(2, minmax(0,1fr)); } }
.dss-oms-stat{
  background:linear-gradient(145deg, #16243A 0%, #101B2D 100%);
  border:1px solid rgba(100, 160, 240, .25);
  border-radius:14px; padding:13px 15px;
  display:flex; flex-direction:column; gap:4px;
}
.dss-oms-stat span{
  font-size:.6rem; text-transform:uppercase; letter-spacing:.09em;
  color:#93C5FD; font-weight:700;
}
.dss-oms-stat b{
  font-size:1.1rem; color:#F8FAFC; font-weight:800;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em;
}
.dss-oms-stat small{
  font-size:.68rem; color:#94A3B8; font-weight:500;
}
.dss-asset-top{ display:flex; justify-content:space-between; align-items:center; gap:6px; margin-bottom:8px; }
.dss-asset-abc{
  display:inline-flex; align-items:center; gap:5px;
  padding:3px 8px; border-radius:6px;
  background:rgba(56, 189, 248, .12); border:1px solid rgba(56, 189, 248, .28);
  font-size:.59rem; letter-spacing:.08em; text-transform:uppercase;
  color:#BAE6FD; font-weight:700;
}
.dss-asset-head-row{
  display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-bottom:9px;
}
.dss-asset-name{
  font-size:1.18rem; font-weight:800; color:#F8FAFC;
  letter-spacing:-.02em; margin:0;
}
.dss-asset-sub{
  font-size:.66rem; color:#93C5FD; font-weight:600;
}
.dss-order-hero{
  background:linear-gradient(135deg, rgba(30, 58, 95, .72) 0%, rgba(17, 38, 68, .62) 100%);
  border:1px solid rgba(56, 189, 248, .30);
  border-radius:12px; padding:10px 12px; margin-bottom:10px;
  display:flex; justify-content:space-between; align-items:center; gap:8px;
}
.dss-order-hero-col{ display:flex; flex-direction:column; gap:2px; }
.dss-order-hero-col span{
  font-size:.56rem; text-transform:uppercase; letter-spacing:.08em;
  color:#93C5FD; font-weight:700;
}
.dss-order-hero-col b{
  font-size:.98rem; font-weight:800; color:#F8FAFC;
  font-variant-numeric:tabular-nums;
}
.dss-order-hero-col b.copper{ color:#34D399; }
.dss-order-hero-col small{
  font-size:.61rem; color:#CBD5E1; font-variant-numeric:tabular-nums;
}
.dss-order-bar-wrap{ margin-bottom:10px; }
.dss-order-bar-head{
  display:flex; justify-content:space-between; align-items:center;
  font-size:.63rem; color:#CBD5E1; margin-bottom:5px;
}
.dss-order-bar-head b{ color:#F8FAFC; font-variant-numeric:tabular-nums; }
.dss-order-bar-track{
  width:100%; height:6px; border-radius:999px;
  background:#0B1322; overflow:hidden; border:1px solid rgba(148,163,184,.14);
}
.dss-order-bar-fill{
  height:100%; border-radius:999px; transition:width .3s ease;
}
.dss-asset-metrics{
  display:grid; grid-template-columns:1fr 1fr; gap:6px 10px;
  padding:8px 10px; border-radius:10px;
  background:rgba(15, 25, 42, .68); border:1px solid rgba(148, 163, 184, .12);
  margin-bottom:8px;
}
.dss-asset-metrics div{ display:flex; flex-direction:column; gap:1px; }
.dss-asset-metrics span{
  font-size:.55rem; text-transform:uppercase; letter-spacing:.07em;
  color:#94A3B8; font-weight:600;
}
.dss-asset-metrics b{
  font-size:.76rem; color:#F1F5F9; font-weight:650;
  font-variant-numeric:tabular-nums;
}
.dss-asset-foot{
  display:flex; justify-content:space-between; align-items:center;
  font-size:.65rem; color:#94A3B8; gap:8px; margin-top:2px; padding-bottom:4px;
}
.dss-asset-foot b{ color:#E2E8F0; font-weight:700; font-variant-numeric:tabular-nums; }
.dss-asset-cost{
  margin-top:6px; padding-top:7px;
  border-top:1px dashed rgba(148, 163, 184, .22);
  display:flex; justify-content:space-between; align-items:center; gap:8px;
}
.dss-asset-cost span{
  font-size:.58rem; text-transform:uppercase; letter-spacing:.07em;
  color:#94A3B8; font-weight:700;
}
.dss-asset-cost b{
  font-size:.78rem; color:#38BDF8; font-weight:750;
  font-variant-numeric:tabular-nums;
}

/* ---------------- Metadatos del modelo matemático ---------------- */
.dss-model-meta{
  display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 4px;
}
.dss-model-meta-item{
  display:flex; flex-direction:column; gap:2px; min-width:92px;
  padding:9px 12px; border-radius:11px;
  background:#0D1524; border:1px solid var(--dss-border);
}
.dss-model-meta-item span{
  font-size:.56rem; text-transform:uppercase; letter-spacing:.1em;
  color:var(--dss-faint); font-weight:700;
}
.dss-model-meta-item b{
  font-size:.78rem; color:var(--dss-text); font-weight:700; font-variant-numeric:tabular-nums;
}

/* Iconos monocromos (máscara CSS) */
.dss-ico{
  display:inline-block; width:1em; height:1em; flex:0 0 auto;
  background:currentColor;
  -webkit-mask:var(--ico) center / contain no-repeat;
          mask:var(--ico) center / contain no-repeat;
}

/* Icono de atención animado en rojo */
.dss-alert-icon{
  position:relative; width:38px; height:38px; flex:0 0 38px;
  display:grid; place-items:center; border-radius:12px;
  color:#FF4D4D;
  background:rgba(255,77,77,.14); border:1px solid rgba(255,77,77,.32);
}
.dss-alert-icon .dss-ico{ width:20px; height:20px; animation:dssAttention 2.4s ease-in-out infinite; transform-origin:50% 60%; }
.dss-alert--warn .dss-alert-icon{
  color:#FF5252;
  background:rgba(255,82,82,.14); border-color:rgba(255,82,82,.32);
}
@keyframes dssAttention{
  0%,100%{ transform:scale(1) rotate(0deg); }
  8%{ transform:scale(1.12) rotate(-6deg); }
  16%{ transform:scale(1.12) rotate(6deg); }
  24%{ transform:scale(1) rotate(0deg); }
}

/* Movimiento reducido por accesibilidad */
@media (prefers-reduced-motion:reduce){
  .dss-ticker{ overflow-x:auto; -webkit-mask-image:none; mask-image:none; }
  .dss-ticker-track,
  .dss-alert-icon .dss-ico{ animation:none !important; }
}

/* ---------------- Avisos / exportación ---------------- */
.dss-notice{
  display:flex; gap:12px; align-items:flex-start; border-radius:14px;
  padding:14px 16px; margin:6px 0 18px;
  background:var(--dss-surface);
  border:1px solid var(--dss-border); font-size:.81rem; color:var(--dss-text-2);
}
.dss-notice-icon{ color:var(--dss-cyan); flex:0 0 auto; }
.dss-notice-icon .dss-ico{ width:20px; height:20px; }
.dss-notice b{ color:#F4F8FE; }
[class*="st-key-export_"]{
  background:var(--dss-surface);
  border:1px solid var(--dss-border); border-radius:14px;
  padding:15px 16px 13px; height:100%;
  box-shadow:var(--dss-shadow);
}
.dss-export-top{ display:flex; align-items:center; gap:11px; margin-bottom:10px; }
.dss-export-icon{
  width:34px; height:34px; border-radius:10px; flex:0 0 34px;
  display:grid; place-items:center; color:var(--dss-copper);
  background:rgba(242,180,92,.10); border:1px solid rgba(242,180,92,.26);
}
.dss-export-icon .dss-ico{ width:17px; height:17px; }
.dss-export-title{ font-size:.85rem; font-weight:650; color:#F4F8FE; }
.dss-export-sub{ font-size:.71rem; color:var(--dss-muted); margin-top:2px; }

/* ---------------- Login Corporativo Ejecutivo (Una Sola Imagen) ---------------- */
.dss-auth-spacer{ height:2.5vh; }
.st-key-auth_card{
  background:var(--dss-surface);
  border:1px solid var(--dss-border);
  border-radius:22px;
  padding:28px 34px 24px;
  box-shadow:0 28px 64px -28px rgba(0,0,0,.92);
  position:relative; overflow:hidden;
}
.dss-auth-top-meta{
  display:flex; justify-content:space-between; align-items:center;
  gap:10px; margin-bottom:10px;
}
.dss-auth-tag{
  font-size:.63rem; letter-spacing:.16em; text-transform:uppercase;
  color:var(--dss-copper); font-weight:700;
  padding:5px 11px; border-radius:999px;
  background:rgba(242,180,92,.10); border:1px solid rgba(242,180,92,.26);
}
.dss-auth-hero-box{
  width:100%; padding:10px 8px 6px;
  display:flex; justify-content:center; align-items:center;
  margin-bottom:8px;
}
.dss-auth-hero-img{
  width:100%; max-width:300px; max-height:142px;
  height:auto; object-fit:contain; display:block;
  filter:drop-shadow(0 12px 24px rgba(0,0,0,.5));
}
.dss-auth-head{ text-align:center; position:relative; z-index:1; margin-bottom:12px; }
.dss-auth-step{
  display:inline-block; margin-bottom:8px; padding:3px 10px; border-radius:999px;
  font-size:.62rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
  color:var(--dss-copper); background:rgba(242,180,92,.10); border:1px solid rgba(242,180,92,.24);
}
.dss-auth-eyebrow{
  font-size:.62rem; letter-spacing:.22em; text-transform:uppercase;
  color:var(--dss-copper); font-weight:700;
}
.dss-auth-title{ font-size:1.4rem; font-weight:800; color:#F7FAFF; letter-spacing:-.03em; margin-top:4px; }
.dss-auth-sub{ font-size:.79rem; color:var(--dss-muted); margin-top:5px; line-height:1.45; }
.dss-auth-models{
  display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px;
  margin-top:8px;
}
.dss-auth-model-badge{
  background:#0D1524; border:1px solid var(--dss-border);
  border-radius:10px; padding:8px 10px; text-align:center;
}
.dss-auth-model-badge span{
  display:block; font-size:.55rem; text-transform:uppercase;
  letter-spacing:.12em; color:var(--dss-faint); font-weight:700;
}
.dss-auth-model-badge b{
  display:block; font-size:.73rem; color:var(--dss-text-2); font-weight:700; margin-top:2px;
}
.dss-auth-hint{
  margin:10px 0 6px; padding:10px 12px; border-radius:10px;
  background:#0D1524; border:1px solid var(--dss-border);
  font-size:.72rem; color:var(--dss-muted); text-align:center; line-height:1.45;
}
.dss-auth-hint b{ color:var(--dss-text); font-weight:600; }
.dss-auth-mail-box{
  margin:4px 0 14px; padding:14px 16px; border-radius:12px;
  background:#0D1524; border:1px solid rgba(61,220,151,.28);
  text-align:center;
}
.dss-auth-mail-title{ font-size:.82rem; font-weight:700; color:#9BEFC8; }
.dss-auth-mail-sub{ font-size:.73rem; color:var(--dss-muted); margin-top:4px; line-height:1.4; }
.dss-auth-code-pill{
  display:inline-block; margin-top:10px; padding:6px 18px; border-radius:8px;
  background:rgba(242,180,92,.12); border:1px solid rgba(242,180,92,.32);
  color:#F7D9A8; font-size:1.15rem; font-weight:800; letter-spacing:.24em;
  font-variant-numeric:tabular-nums;
}

/* ---------------- Reloj Dinámico Anti-DDoS y Panel OTP 6 Dígitos ---------------- */
@keyframes dss-pulse-red{
  0%, 100%{ box-shadow:0 0 0 0 rgba(255, 82, 82, .45); }
  50%{ box-shadow:0 0 0 8px rgba(255, 82, 82, 0); }
}
@keyframes dss-blink{
  0%, 100%{ opacity:1; }
  50%{ opacity:.25; }
}
.dss-lock-card{
  margin:6px 0 14px; padding:16px 18px; border-radius:16px;
  background:linear-gradient(145deg, rgba(48, 16, 26, .92) 0%, rgba(22, 12, 20, .96) 100%);
  border:1px solid rgba(255, 92, 92, .45);
  box-shadow:0 18px 36px -20px rgba(255, 59, 59, .35);
  text-align:center;
}
.dss-lock-kicker{
  display:inline-flex; align-items:center; gap:7px;
  padding:4px 11px; border-radius:999px;
  background:rgba(255, 82, 82, .15); border:1px solid rgba(255, 82, 82, .38);
  font-size:.62rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase;
  color:#FF8080; margin-bottom:8px;
}
.dss-lock-dot{
  width:7px; height:7px; border-radius:50%; background:#FF4D4D;
  animation:dss-pulse-red 1.4s infinite;
}
.dss-lock-title{
  font-size:.9rem; font-weight:750; color:#FFF0F0; margin-bottom:4px;
}
.dss-lock-sub{
  font-size:.73rem; color:#FCA5A5; line-height:1.4; margin-bottom:12px;
}
.dss-lock-clock{
  display:flex; justify-content:center; align-items:center; gap:10px;
  margin:8px 0 12px;
}
.dss-lock-unit{
  min-width:68px; padding:8px 12px; border-radius:12px;
  background:#0B0F1A; border:1px solid rgba(255, 107, 107, .38);
  box-shadow:inset 0 2px 8px rgba(0,0,0,.6);
  display:flex; flex-direction:column; align-items:center;
}
.dss-lock-num{
  font-family:"JetBrains Mono", monospace;
  font-size:1.55rem; font-weight:800; color:#FF5252;
  line-height:1.1; font-variant-numeric:tabular-nums;
}
.dss-lock-lbl{
  font-size:.55rem; text-transform:uppercase; letter-spacing:.12em;
  color:#FDA4AF; font-weight:700; margin-top:3px;
}
.dss-lock-sep{
  font-family:"JetBrains Mono", monospace;
  font-size:1.45rem; font-weight:800; color:#FF6B6B;
  animation:dss-blink 1s steps(2, start) infinite;
}
.dss-lock-bar-track{
  width:100%; height:6px; border-radius:999px;
  background:rgba(11, 15, 26, .85); overflow:hidden;
  border:1px solid rgba(255, 107, 107, .22);
}
.dss-lock-bar-fill{
  height:100%; border-radius:999px;
  background:linear-gradient(90deg, #FF4D4D 0%, #F97316 100%);
  transition:width .6s linear;
}

.dss-otp-card{
  margin:4px 0 12px; padding:15px 16px 13px; border-radius:16px;
  background:linear-gradient(155deg, #152338 0%, #0E1726 100%);
  border:1px solid rgba(56, 189, 248, .32);
  box-shadow:0 16px 32px -22px rgba(14, 165, 233, .35);
  text-align:center;
}
.dss-otp-badge-row{
  display:flex; justify-content:space-between; align-items:center;
  gap:8px; margin-bottom:10px; flex-wrap:wrap;
}
.dss-otp-mail-pill{
  display:inline-flex; align-items:center; gap:6px;
  padding:4px 10px; border-radius:999px;
  background:rgba(16, 185, 129, .12); border:1px solid rgba(16, 185, 129, .32);
  color:#6EE7B7; font-size:.66rem; font-weight:700;
}
.dss-otp-timer-pill{
  display:inline-flex; align-items:center; gap:6px;
  padding:4px 10px; border-radius:999px;
  background:rgba(56, 189, 248, .12); border:1px solid rgba(56, 189, 248, .3);
  color:#7DD3FC; font-family:"JetBrains Mono", monospace;
  font-size:.68rem; font-weight:700; font-variant-numeric:tabular-nums;
}
.dss-otp-slots{
  display:flex; justify-content:center; align-items:center; gap:7px;
  margin:10px 0 10px;
}
.dss-otp-slot{
  width:38px; height:44px; border-radius:10px;
  background:#09111E; border:1px solid rgba(56, 189, 248, .38);
  display:grid; place-items:center;
  font-family:"JetBrains Mono", monospace;
  font-size:1.15rem; font-weight:800; color:#38BDF8;
  box-shadow:inset 0 2px 6px rgba(0,0,0,.55), 0 0 12px -4px rgba(56, 189, 248, .25);
}
.dss-otp-slot-sep{
  color:#64748B; font-weight:800; font-size:1rem; padding:0 2px;
}
.dss-otp-meta{
  display:flex; justify-content:space-between; align-items:center;
  font-size:.68rem; color:#94A3B8; padding-top:8px;
  border-top:1px dashed rgba(148, 163, 184, .18);
}
.dss-otp-meta b{ color:#F8FAFC; font-variant-numeric:tabular-nums; }

.st-key-otp_input_wrap input[type="text"]{
  font-family:"JetBrains Mono", monospace !important;
  font-size:1.65rem !important;
  font-weight:800 !important;
  letter-spacing:.55em !important;
  text-align:center !important;
  color:#F8FAFC !important;
  background:#09111E !important;
  border:1.5px solid rgba(56, 189, 248, .48) !important;
  border-radius:14px !important;
  padding:14px 16px 14px 26px !important;
  height:58px !important;
  box-shadow:0 0 22px -8px rgba(56, 189, 248, .38) !important;
}
.st-key-otp_input_wrap input[type="text"]:focus{
  border-color:#F2B45C !important;
  box-shadow:0 0 26px -6px rgba(242, 180, 92, .52) !important;
}
.st-key-otp_input_wrap input[type="text"]::placeholder{
  color:rgba(148, 163, 184, .28) !important;
  letter-spacing:.55em !important;
}
.dss-auth-foot{
  text-align:center; font-size:.66rem; color:var(--dss-faint);
  margin-top:14px; line-height:1.6;
}
.dss-auth-foot-copy{ margin-top:8px; font-size:.68rem; color:var(--dss-muted); }
.dss-auth-foot .dss-chip{ font-size:.6rem; padding:3px 8px; }
.st-key-auth_card [data-testid="stBaseButton-tertiary"]{
  background:transparent; border-color:transparent; box-shadow:none;
  color:var(--dss-muted); font-weight:600; font-size:.8rem; padding:4px 2px;
  transform:none;
}
.st-key-auth_card [data-testid="stBaseButton-tertiary"]:hover{
  color:var(--dss-copper); background:transparent; border-color:transparent;
  box-shadow:none; transform:none;
}
.st-key-auth_card [data-testid="stAlertContainer"]{ font-size:.82rem; }

/* ---------------- Responsive ---------------- */
@media (max-width:1360px){
  .dss-kpi-grid{ grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:1000px){
  /* Las dos gráficas, el login split-screen y los exportadores pasan a una sola columna. */
  [data-testid="stHorizontalBlock"]:has([class*="st-key-card_"]),
  [data-testid="stHorizontalBlock"]:has([class*="st-key-export_"]),
  [data-testid="stHorizontalBlock"]:has(.st-key-auth_showcase){
    flex-direction:column !important;
    gap:14px !important;
  }
  [data-testid="stHorizontalBlock"]:has([class*="st-key-card_"]) > [data-testid="stColumn"],
  [data-testid="stHorizontalBlock"]:has([class*="st-key-export_"]) > [data-testid="stColumn"],
  [data-testid="stHorizontalBlock"]:has(.st-key-auth_showcase) > [data-testid="stColumn"]{
    width:100% !important;
    flex:1 1 100% !important;
    max-width:100% !important;
  }
  .dss-showcase-grid{ grid-template-columns:1fr; }
}
@media (max-width:740px){
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-asset_"]){
    grid-template-columns:repeat(2, minmax(0, 1fr)) !important;
  }
}
@media (max-width:560px){
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-asset_"]){
    grid-template-columns:1fr !important;
  }
}
@media (max-width:900px){
  [data-testid="stMainBlockContainer"], .block-container{ padding:1rem 1.1rem 2.5rem !important; }
  .dss-topbar{ flex-direction:column; align-items:flex-start; padding:15px 16px; }
  .dss-topbar-meta{ width:100%; justify-content:space-between; gap:14px; }
  .dss-topbar-title{ font-size:1.18rem; }
  .dss-section{ flex-wrap:wrap; gap:10px; }
  .dss-section-line{ display:none; }
  .dss-alert-head{ flex-direction:column; }
  .dss-ok-wrap{ flex-wrap:wrap; }
  .dss-ok-side{ margin-left:0; }
  .dss-kpi-grid{ grid-template-columns:1fr; }
}
@media (max-width:680px){
  .dss-kpi{ min-height:140px; }
  .dss-spark{ width:78px; bottom:44px; }
  .dss-meta-item b{ font-size:.78rem; }
  .dss-alert{ padding:15px 15px 12px; }
  .dss-subhead{ flex-direction:column; align-items:flex-start; gap:6px; }
  .st-key-auth_card{ padding:26px 20px 20px; }
}
</style>
"""


def inyectar_estilos() -> None:
    """Inyecta el CSS global del dashboard (idempotente por sesión de render)."""

    st.markdown(_CSS, unsafe_allow_html=True)
