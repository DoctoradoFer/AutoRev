# --- CONFIGURACIÓN DE LA PÁGINA ---
import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import time

st.set_page_config(page_title="Verificador de Transparencia", page_icon="🔍")

st.title("🔍 Verificador de Hipervínculos de Transparencia")
st.markdown("""
Esta herramienta analiza tus formatos de obligaciones de transparencia (Excel),
extrae los enlaces y verifica si están **ACTIVOS** o **ROTOS**.
""")

# --- FUNCIÓN DE VERIFICACIÓN (NUESTRO MOTOR) ---
def verificar_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        # Timeout corto para demostración, idealmente 5-10s
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=5)
        if response.status_code == 405:
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=5, stream=True)
        
        if response.status_code == 200:
            return "✅ ACTIVO", "OK"
        elif response.status_code == 404:
            return "❌ ROTO (404)", "ERROR"
        else:
            return f"⚠️ ESTADO {response.status_code}", "WARNING"
    except:
        return "💀 ERROR DE CONEXIÓN", "ERROR"

# --- INTERFAZ DE USUARIO ---

# 1. Widget para subir el archivo
archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.info("Archivo cargado exitosamente. Analizando estructura...")
    
    # Botón para iniciar el proceso
    if st.button("Iniciar Verificación de Enlaces"):
        
        # Leemos el Excel
        wb = load_workbook(archivo_subido, data_only=False)
        ws = wb.active
        
        lista_enlaces = []
        barra_progreso = st.progress(0)
        status_text = st.empty()
        
        # Estimación básica de filas para la barra de progreso
        total_filas = ws.max_row
        fila_actual = 0

        # Escaneo
        for row in ws.iter_rows():
            fila_actual += 1
            # Actualizamos barra de progreso (normalizada 0-100)
            progreso = min(int((fila_actual / total_filas) * 100), 100)
            barra_progreso.progress(progreso)
            
            for cell in row:
                url_encontrada = None
                
                # Detectar Hipervínculo incrustado o texto
                if cell.hyperlink:
                    url_encontrada = cell.hyperlink.target
                elif isinstance(cell.value, str) and str(cell.value).startswith(('http://', 'https://')):
                    url_encontrada = cell.value
                
                # Si hay URL, verificamos
                if url_encontrada:
                    status_text.text(f"Verificando: {url_encontrada[:50]}...")
                    estado_texto, tipo_estado = verificar_url(url_encontrada)
                    
                    lista_enlaces.append({
                        "Coordenada": cell.coordinate,
                        "URL Original": url_encontrada,
                        "Estado": estado_texto
                    })

        barra_progreso.progress(100)
        status_text.text("¡Verificación completada!")
        
        # --- MOSTRAR RESULTADOS ---
        if lista_enlaces:
            df_resultados = pd.DataFrame(lista_enlaces)
            
            # Métricas rápidas
            col1, col2 = st.columns(2)
            col1.metric("Total Enlaces", len(df_resultados))
            rotos = len(df_resultados[df_resultados['Estado'].str.contains("ROTO|ERROR")])
            col2.metric("Enlaces Rotos", rotos, delta_color="inverse")
            
            st.dataframe(df_resultados)
            
            # --- DESCARGAR REPORTE ---
            # Convertimos el DF a CSV para descarga
            csv = df_resultados.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Descargar Reporte de Errores",
                data=csv,
                file_name="reporte_transparencia.csv",
                mime="text/csv",
            )
        else:

            st.warning("No se encontraron hipervínculos en este archivo.")
