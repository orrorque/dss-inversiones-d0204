import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

warnings.filterwarnings("ignore")


def obtener_z_score(nivel_servicio):
    niveles = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
    return niveles.get(nivel_servicio, 1.65)


def factor_mercado_cobre(precio_cobre_actual, precio_cobre_promedio, precio_cobre_proyectado=None):
    """
    Determina el factor de ajuste financiero del lote EOQ según la cotización
    internacional del cobre (LME / HG=F) frente a su media histórica y tendencia.
    """
    if precio_cobre_promedio <= 0:
        return 1.0, "Estándar (1.00x)", "neutral"

    ratio = precio_cobre_actual / precio_cobre_promedio
    alza_proyectada = (
        precio_cobre_proyectado is not None
        and precio_cobre_proyectado > precio_cobre_actual * 1.015
    )

    if ratio < 0.95:
        return 1.15, "Descuento LME (+15% EOQ)", "success"
    if ratio > 1.05:
        return 0.85, "Sobreprecio LME (-15% EOQ)", "warning"
    if alza_proyectada:
        return 1.08, "Cobertura Alcista (+8% EOQ)", "info"
    return 1.00, "Banda Neutral LME (1.00x)", "copper"


def calcular_eoq(
    demanda_anual,
    costo_pedido,
    tasa_mantenimiento,
    costo_unitario,
    precio_cobre_actual,
    precio_cobre_promedio,
    capacidad_maxima,
    stock_actual,
    precio_cobre_proyectado=None,
):
    costo_mant_real = tasa_mantenimiento * costo_unitario
    if costo_mant_real <= 0:
        return 0.0

    eoq_base = np.sqrt((2 * demanda_anual * costo_pedido) / costo_mant_real)
    factor_lme, _, _ = factor_mercado_cobre(
        precio_cobre_actual, precio_cobre_promedio, precio_cobre_proyectado
    )
    eoq_final = eoq_base * factor_lme

    if (eoq_final + stock_actual) > capacidad_maxima:
        eoq_final = max(0.0, capacidad_maxima - stock_actual)

    return float(eoq_final)


def calcular_stock_seguridad(
    demanda_anual,
    dias_entrega,
    nivel_servicio,
    desviacion_demanda,
    desviacion_entrega,
):
    demanda_diaria = demanda_anual / 365.0
    z = obtener_z_score(nivel_servicio)

    # Stock de Seguridad con variabilidad dual (Demanda de planta y Lead Time de proveedor)
    varianza_demanda = dias_entrega * (desviacion_demanda ** 2)
    varianza_entrega = (demanda_diaria ** 2) * (desviacion_entrega ** 2)
    return float(z * np.sqrt(varianza_demanda + varianza_entrega))


def calcular_rop(
    demanda_anual,
    dias_entrega,
    nivel_servicio,
    desviacion_demanda,
    desviacion_entrega,
):
    demanda_diaria = demanda_anual / 365.0
    stock_seguridad = calcular_stock_seguridad(
        demanda_anual,
        dias_entrega,
        nivel_servicio,
        desviacion_demanda,
        desviacion_entrega,
    )
    return float((demanda_diaria * dias_entrega) + stock_seguridad)


def pronosticar_serie(serie_historica, meses_proyeccion=1):
    serie = serie_historica.copy()
    serie.index = pd.to_datetime(serie.index)
    # Limpieza de serie: se reindexa mes a mes y se descartan periodos sin datos
    serie = serie.asfreq("MS").dropna()
    if len(serie) == 0:
        idx = pd.date_range(start="2025-11-01", periods=meses_proyeccion, freq="MS")
        return pd.Series(np.nan, index=idx, dtype=float)
    valores = serie.values.astype(float)
    limpio = valores[~np.isnan(valores)]
    ser_clean = pd.Series(limpio, index=pd.RangeIndex(len(limpio)))
    modelo = SimpleExpSmoothing(ser_clean, initialization_method="estimated").fit()
    return modelo.forecast(meses_proyeccion).round(2)


def evaluar_modelo_calibre(
    calibre,
    stock_actual,
    demanda_anual_base,
    costo_unitario_base,
    serie_salidas_calibre,
    precio_cobre_actual,
    precio_cobre_promedio,
    precio_cobre_proyectado,
    config,
):
    """
    Integra en un único modelo matemático para toma de decisiones:
    1) Salida/venta histórica y proyectada del calibre en la empresa (SES).
    2) Cotización internacional del cobre (LME / HG=F) y su diferencial.
    3) Punto de quiebre de stock (ROP), stock de seguridad, autonomía y déficit.
    4) Lote económico de compra (EOQ) ajustado al mercado internacional e inversión.
    """
    # 1. Dinámica de ventas/salidas internas de la empresa
    salida_ultimo_mes = float(serie_salidas_calibre.iloc[-1])
    salida_promedio_mes = float(serie_salidas_calibre.mean())
    desviacion_mensual = float(serie_salidas_calibre.std())
    salida_proyectada_mes = float(pronosticar_serie(serie_salidas_calibre, 1).iloc[0])

    variacion_salida_pct = (
        ((salida_proyectada_mes / salida_ultimo_mes) - 1.0) * 100.0
        if salida_ultimo_mes > 0
        else 0.0
    )

    # Demanda efectiva anualizada ponderando base anual (70 %) y proyección de salidas (30 %)
    demanda_anual_proyectada = salida_proyectada_mes * 12.0
    demanda_efectiva = round((0.70 * float(demanda_anual_base)) + (0.30 * demanda_anual_proyectada), 2)
    demanda_diaria = demanda_efectiva / 365.0

    # 2. Indexación al precio del mercado internacional del cobre (LME)
    variacion_lme_pct = (
        ((precio_cobre_actual - precio_cobre_promedio) / precio_cobre_promedio) * 100.0
        if precio_cobre_promedio > 0
        else 0.0
    )
    # Sensibilidad de costo unitario ante variaciones del cobre internacional (elasticidad 0.35)
    factor_costo_lme = 1.0 + (0.35 * (variacion_lme_pct / 100.0))
    costo_unitario_lme = round(float(costo_unitario_base) * max(0.85, min(1.20, factor_costo_lme)), 2)

    factor_lme, regimen_lme, variante_lme = factor_mercado_cobre(
        precio_cobre_actual, precio_cobre_promedio, precio_cobre_proyectado
    )

    # 3. Modelo de quiebre de stock (ROP y Stock de Seguridad)
    stock_seguridad = calcular_stock_seguridad(
        demanda_anual_base,
        config["dias_entrega"],
        config["nivel_servicio"],
        desviacion_mensual,
        config["desviacion_entrega"],
    )
    rop = calcular_rop(
        demanda_anual_base,
        config["dias_entrega"],
        config["nivel_servicio"],
        desviacion_mensual,
        config["desviacion_entrega"],
    )

    dias_autonomia = (stock_actual / demanda_diaria) if demanda_diaria > 0 else 0.0
    cobertura_rop_pct = (stock_actual / rop * 100.0) if rop > 0 else 100.0
    deficit_kg = max(0.0, rop - stock_actual)
    holgura_kg = max(0.0, stock_actual - rop)

    # 4. Lote óptimo de compra (EOQ) e inversión requerida
    costo_mant_unit = config["tasa_mantenimiento"] * costo_unitario_base
    eoq_wilson_base = (
        float(np.sqrt((2.0 * demanda_anual_base * config["costo_pedido"]) / costo_mant_unit))
        if costo_mant_unit > 0
        else 0.0
    )
    eoq = calcular_eoq(
        demanda_anual_base,
        config["costo_pedido"],
        config["tasa_mantenimiento"],
        costo_unitario_base,
        precio_cobre_actual,
        precio_cobre_promedio,
        config["capacidad_max"],
        stock_actual,
        precio_cobre_proyectado,
    )

    inversion_orden = round(eoq * costo_unitario_lme, 2)
    estado = "CRÍTICO" if stock_actual <= rop else "ESTABLE"

    if stock_actual <= rop:
        prioridad_accion = "EMISIÓN INMEDIATA"
    elif stock_actual <= rop * 1.15:
        prioridad_accion = "COMPRA PREVENTIVA"
    else:
        prioridad_accion = "STOCK EN RANGO"

    return {
        "Calibre": calibre,
        "Stock Físico": int(stock_actual),
        "Punto de Quiebre (ROP)": round(rop, 2),
        "Stock Seguridad (SS)": round(stock_seguridad, 2),
        "Déficit Quiebre (kg)": round(deficit_kg, 2),
        "Holgura ROP (kg)": round(holgura_kg, 2),
        "Cobertura ROP (%)": round(cobertura_rop_pct, 1),
        "Autonomía (Días)": round(dias_autonomia, 1),
        "Salida Últ. Mes (kg)": round(salida_ultimo_mes, 0),
        "Salida Prom. Mes (kg)": round(salida_promedio_mes, 1),
        "Salida Proy. Mes (kg)": round(salida_proyectada_mes, 1),
        "Var. Salida (%)": round(variacion_salida_pct, 1),
        "Demanda Anual": int(demanda_anual_base),
        "Demanda Efectiva (kg)": demanda_efectiva,
        "EOQ Base Wilson (kg)": round(eoq_wilson_base, 2),
        "Factor LME": factor_lme,
        "Régimen LME": regimen_lme,
        "Variante LME": variante_lme,
        "Sugerencia Compra (EOQ)": round(eoq, 2),
        "Costo Unitario": round(float(costo_unitario_base), 2),
        "Costo Indexado LME ($)": costo_unitario_lme,
        "Inversión Orden ($)": inversion_orden,
        "Acción Sugerida": prioridad_accion,
        "Estatus": estado,
    }
