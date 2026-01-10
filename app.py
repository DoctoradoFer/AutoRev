import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook

# --- CONFIGURACIÓN DE LA PÁGINA (Debe ser la primera instrucción de Streamlit) ---
st.set_page_config(page_title="Verificador de Transparencia", page_icon="🔍")

# --- BARRA LATERAL CON CRÉDITOS ---
with st.sidebar:
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
    st.write("---")
    st.write("Esta aplicación es de uso académico y gratuito para la verificación de obligaciones de transparencia.")

# --- TÍTULO PRINCIPAL ---
st.title("🔍 Verificador de Hipervínculos de archivos de obligaciones de transparencia")
st.markdown("""
Esta herramienta analiza **todas las hojas** de tus formatos de transparencia (Excel),
extrae los enlaces y verifica si están **ACTIVOS** o **ROTOS**.
""")

# --- FUNCIÓN DE VERIFICACIÓN ---
def verificar_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        # Timeout de 5 segundos
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
archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado correctamente. Haz clic abajo para procesar.")
    
    if st.button("Iniciar Verificación Completa"):
        
        wb = load_workbook(archivo_subido, data_only=False)
        lista_enlaces = []
        barra_progreso = st.progress(0)
        status_text = st.empty()
        
        nombres_hojas = wb.sheetnames
        total_hojas = len(nombres_hojas)
        
        for indice, nombre_hoja in enumerate(nombres_hojas):
            ws = wb[nombre_hoja]
            status_text.text(f"Analizando hoja: {nombre_hoja} ({indice + 1}/{total_hojas})...")
            
            for row in ws.iter_rows():
                for cell in row:
                    url_encontrada = None
                    
                    if cell.hyperlink:
                        url_encontrada = cell.hyperlink.target
                    elif isinstance(cell.value, str) and str(cell.value).startswith(('http://', 'https://')):
                        url_encontrada = cell.value
                    
                    if url_encontrada:
                        estado_texto, tipo_estado = verificar_url(url_encontrada)
                        
                        lista_enlaces.append({
                            "Hoja": nombre_hoja,
                            "Coordenada": cell.coordinate,
                            "URL Original": url_encontrada,
                            "Estado": estado_texto
                        })
            
            progreso = int(((indice + 1) / total_hojas) * 100)
            barra_progreso.progress(progreso)

        status_text.success("¡Verificación completada!")
        
        if lista_enlaces:
            df_resultados = pd.DataFrame(lista_enlaces)
            
            col1, col2 = st.columns(2)
            col1.metric("Total Enlaces", len(df_resultados))
            rotos = len(df_resultados[df_resultados['Estado'].str.contains("ROTO|ERROR")])
            col2.metric("Enlaces Rotos", rotos, delta_color="inverse")
            
            st.dataframe(df_resultados)
            
            csv = df_resultados.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Reporte Completo",
                data=csv,
                file_name="reporte_doctorado_fernando.csv",
                mime="text/csv",
            )
        else:
            st.warning("No se encontraron hipervínculos en el archivo.")

# --- PIE DE PÁGINA ---
st.write("---")
st.markdown("##### 🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
