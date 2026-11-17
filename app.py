import socket
import threading
import streamlit as st
from modules.auth import inicializar_sesion, renderizar_login, renderizar_perfil_usuario


@st.cache_resource
def asegurar_api_en_segundo_plano():
    """Garantiza que la API ASGI (:8501) esté activa incluso en despliegues Cloud de un solo proceso."""
    try:
        with socket.create_connection(("127.0.0.1", 8501), timeout=0.6):
            return True
    except OSError:
        pass
    try:
        import uvicorn
        from api import api as asgi_app

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=8501, log_level="warning")
        server = uvicorn.Server(config)
        hilo = threading.Thread(target=server.run, daemon=True)
        hilo.start()
        return True
    except Exception:
        return False


asegurar_api_en_segundo_plano()
from modules.notifications import procesar_alertas_automaticas
from modules.data_handler import cargar_datos
from modules.theme import inyectar_estilos
from modules.ui_components import (renderizar_panel_lateral, generar_matriz_decisiones,
                                   renderizar_centro_alertas, renderizar_kpis_profesionales,
                                   renderizar_inteligencia_mercado, renderizar_panel_acciones,
                                   renderizar_cabecera, renderizar_aviso_operador,
                                   renderizar_estado_backend, renderizar_consola_admin,
                                   renderizar_modo_carteleria)

st.set_page_config(
    page_title="DSS · Inversiones D-02-04",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inyectar_estilos()
inicializar_sesion()

if not st.session_state['autenticado']:
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none;}</style>",
        unsafe_allow_html=True,
    )
    renderizar_login()
else:
    if st.session_state['rol'] == "Administrador":
        # Consola exclusiva de Soporte del Sistema y Administración de Usuarios
        renderizar_panel_lateral(None)
        renderizar_perfil_usuario()
        renderizar_cabecera()
        renderizar_consola_admin()
    else:
        # 1. Configuración Global Oculta
        CONFIG_LOGISTICA = {
            'dias_entrega': 15, 'costo_pedido': 50.0, 'tasa_mantenimiento': 0.20,
            'nivel_servicio': 0.95, 'capacidad_max': 5000, 'desviacion_entrega': 3
        }

        # 2. Carga y Procesamiento de Datos
        df_inventario, df_hist, df_cobre = cargar_datos()
        df_resultados = generar_matriz_decisiones(df_inventario, df_hist, df_cobre, CONFIG_LOGISTICA)

        # 3. Ejecución de Alertas en Segundo Plano
        procesar_alertas_automaticas(df_resultados)

        # 4. Renderizado Condicional de Interfaz según el Rol y Modo Cartelería
        calibre_sel = renderizar_panel_lateral(df_hist)
        renderizar_perfil_usuario()

        if st.session_state.get("modo_carteleria"):
            renderizar_modo_carteleria(df_resultados, df_inventario, df_hist, df_cobre)
        else:
            renderizar_cabecera()
            renderizar_estado_backend()

            renderizar_centro_alertas(df_resultados)

            if st.session_state['rol'] == "Gerencia":
                # Acceso total corporativo
                renderizar_kpis_profesionales(df_resultados, df_cobre, df_hist)
                renderizar_inteligencia_mercado(df_inventario, df_hist, df_cobre, calibre_sel)
                renderizar_panel_acciones(df_resultados)
            else:
                # Vista restringida para Operaciones (Solo Ejecución)
                renderizar_aviso_operador()
                renderizar_panel_acciones(df_resultados)
