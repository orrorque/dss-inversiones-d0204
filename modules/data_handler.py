import pandas as pd
import os
import re
import numpy as np
import yfinance as yf

RUTA_INVENTARIO_EXCEL = "data/Inventario_PyME.xlsx"

MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


# ---------------------------------------------------------------------------
# Lectura de la base de datos de inventario de la empresa (Excel)
# ---------------------------------------------------------------------------


def obtener_cobre_api():
    # Conexión en tiempo real con el mercado de futuros de materias primas
    ticker = yf.Ticker("HG=F")
    df_cobre = ticker.history(period="1y", interval="1mo")

    # Limpieza de datos y conversión matemática de USD/Libra a USD/Tonelada Métrica
    df_cobre = df_cobre[['Open', 'High', 'Low', 'Close']].dropna()
    df_cobre.index = df_cobre.index.tz_localize(None)
    df_cobre = df_cobre * 2204.62

    # Redondeo para estética financiera
    return df_cobre.round(2)


# ---------------------------------------------------------------------------
# Utilidades de normalización para la base de datos de la empresa (Excel)
# ---------------------------------------------------------------------------

def _normalizar_calibre(valor):
    """Convierte 'Calibre 6', 'Calibre 6 AWG', 6, etc. al estándar '6 AWG'."""
    texto = str(valor).strip()
    limpio = re.sub(r"^calibre\s*", "", texto, flags=re.IGNORECASE).strip()
    return f"{limpio} AWG"


def _a_numero(valor):
    """Fuerza numérico; devuelve None si el valor es nulo o no parseable."""
    try:
        if valor is None or pd.isna(valor):
            return None
        return float(valor)
    except (ValueError, TypeError):
        return None


def _mes_a_datetime(columna):
    """Convierte etiquetas de mes tipo 'Ene-25' a Timestamp (día 1 del mes)."""
    texto = str(columna).strip().lower()
    m = re.fullmatch(r"([a-z]{3})-(\d{2})", texto)
    if not m:
        return None
    mes = MESES_ES.get(m.group(1))
    if mes is None:
        return None
    return pd.Timestamp(year=2000 + int(m.group(2)), month=mes, day=1)


# ---------------------------------------------------------------------------
# Lectura de la base de datos de inventario de la empresa (Excel)
# ---------------------------------------------------------------------------

def _leer_inventario_excel():
    """
    Lee 'Inventario_General' desde data/Inventario_PyME.xlsx.

    Estructura detectada de la hoja:
        Fila 0: Leyenda (texto libre)
        Fila 1: Cabecera  -> Calibre (AWG) | Stock Inicial (kg) | Demanda Actual (kg) | ...
        Fila 2: Datos vacíos / separación
        Filas 3+: Datos de calibre (Calibre 6, Stock Inicial 31, Demanda Actual 27, ...)

    Retorna un DataFrame con las columnas base del DSS:
        Calibre | Stock Actual (kg) | Demanda Anual Est. (kg) | Costo Unitario ($)
    """
    df_raw = pd.read_excel(RUTA_INVENTARIO_EXCEL, sheet_name="Inventario_General", header=None)

    header_idx = None
    for i in range(len(df_raw)):
        if str(df_raw.iloc[i, 0]).strip().lower().startswith("calibre"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("No se encontró la fila de cabecera 'Calibre' en Inventario_PyME.xlsx")

    data = df_raw.iloc[header_idx + 1:].copy()
    data.columns = [str(c).strip() for c in df_raw.iloc[header_idx]]
    data = data.dropna(how="all")

    filas = []
    for _, row in data.iterrows():
        calibre = _normalizar_calibre(row.iloc[0])
        stock = _a_numero(row.iloc[1])   # Stock Inicial (kg)
        demanda = _a_numero(row.iloc[2])  # Demanda Actual (kg)
        costo = _a_numero(row.iloc[6])   # Costo Unitario USD

        if not calibre or stock is None or demanda is None or costo is None:
            continue

        filas.append({
            "Calibre": calibre,
            "Stock Actual (kg)": stock,
            "Demanda Anual Est. (kg)": demanda,
            "Costo Unitario ($)": costo,
        })

    df_inv = pd.DataFrame(
        filas,
        columns=["Calibre", "Stock Actual (kg)", "Demanda Anual Est. (kg)", "Costo Unitario ($)"],
    )
    return df_inv.sort_values("Calibre").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Lectura del histórico de salidas / ventas por calibre (Excel)
# ---------------------------------------------------------------------------

def _leer_historico_excel():
    """
    Lee la hoja 'Historico_Ventas' desde data/Inventario_PyME.xlsx.

    Estructura detectada:
        Columna 0: Calibre (AWG)  -> 'Calibre 6' ... 'Calibre 34'
        Columnas 1..N: Meses en español con año, tipo 'Ene-25', 'Feb-25', ..., 'Ago-26'

    Retorna un DataFrame con:
        Index:    datetime64 (Mes, día 1 de cada mes)
        Columns:  calibre normalizado (6 AWG, 7 AWG, ...)
        Valores:  kg salidas por mes.
    """
    df = pd.read_excel(RUTA_INVENTARIO_EXCEL, sheet_name="Historico_Ventas")
    df.columns = [str(c).strip() for c in df.columns]

    series = {}
    for _, row in df.iterrows():
        calibre = _normalizar_calibre(row.iloc[0])
        valores = {}
        for i, col in enumerate(df.columns[1:], start=1):
            ts = _mes_a_datetime(col)
            valor = _a_numero(row.iloc[i])
            if ts is not None and valor is not None:
                valores[ts] = valor
        if valores:
            series[calibre] = pd.Series(valores, name=calibre)

    if not series:
        return pd.DataFrame()

    fechas = sorted({ts for s in series.values() for ts in s.index})
    datos = {
        calibre: [serie.get(ts, np.nan) for ts in fechas]
        for calibre, serie in series.items()
    }
    df_hist = pd.DataFrame(datos, index=pd.DatetimeIndex(fechas, name="Mes"))
    return df_hist.astype(float)


# ---------------------------------------------------------------------------
# Punto de entrada de datos del DSS
# ---------------------------------------------------------------------------

def cargar_datos():
    """
    Carga la base de datos de inventario de la empresa (Excel) + API de cobre.
    Fuente única: data/Inventario_PyME.xlsx
    """
    df_inv = _leer_inventario_excel()
    df_hist = _leer_historico_excel()

    # Se inyecta la API viva directamente al flujo del DSS
    df_cobre = obtener_cobre_api()
    return df_inv, df_hist, df_cobre
