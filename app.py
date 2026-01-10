import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Verificador de archivos de obligaciones de Transparencia", page_icon="🔍", layout="wide")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
    st.write("---")
    st.write("Esta aplicación utiliza procesamiento paralelo para verificar múltiples enlaces simultáneamente.")

# --- TÍTULO ---
st.title("🚀 Verificador de Hipervínculos (Modo Turbo)")
st.markdown("""
Esta herramienta analiza tus formatos de transparencia (Excel), extrae los enlaces
y verifica si están **ACTIVOS** o **ROTOS** de forma masiva y rápida.
""")

# --- FUNCIÓN DE VERIFICACIÓN ---
def verificar_un_enlace(datos_enlace):
    url = datos_enlace['URL Original']
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        # Timeout reducido a 3s para agilizar, ya que vamos en paralelo
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=3)
        if response.status_code == 405:
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=3, stream=True)
        
        if response.status_code == 200:
            datos_enlace['Estado'] = "✅ ACTIVO"
        elif response.status_code == 404:
            datos_enlace['Estado'] = "❌ ROTO (404)"
        else:
            datos_enlace['Estado'] = f"⚠️ ESTADO {response.status_code}"
            
    except:
        datos_enlace['Estado'] = "💀 ERROR DE CONEXIÓN"
    
    return datos_enlace

# --- INTERFAZ ---
archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado. Preparando motores...")
    
    if st.button("Iniciar Verificación Rápida"):
        
        # 1. FASE DE ESCANEO (Lectura del Excel)
        st.write("📂 Escaneando archivo en busca de enlaces...")
        wb = load_workbook(archivo_subido, data_only=False)
        lista_cruda = []
        
        for nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            for row in ws.iter_rows():
                for cell in row:
                    url_encontrada = None
                    if cell.hyperlink:
                        url_encontrada = cell.hyperlink.target
                    elif isinstance(cell.value, str) and str(cell.value).startswith(('http://', 'https://')):
                        url_encontrada = cell.value
                    
                    if url_encontrada:
                        lista_cruda.append({
                            "Hoja": nombre_hoja,
                            "Coordenada": cell.coordinate,
                            "URL Original": url_encontrada,
                            "Estado": "Pendiente"
                        })
        
        total_enlaces = len(lista_cruda)
        st.info(f"Se encontraron {total_enlaces} enlaces. Iniciando verificación masiva...")
        
        # 2. FASE DE PROCESAMIENTO PARALELO
        resultados_finales = []
        barra = st.progress(0)
        texto_estado = st.empty()
        
        # Usamos ThreadPoolExecutor para lanzar 10 verificaciones a la vez
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Mandamos todos los enlaces a la fila de procesamiento
            futures = {executor.submit(verificar_un_enlace, item): item for item in lista_cruda}
            
            completados = 0
            for future in concurrent.futures.as_completed(futures):
                item_procesado = future.result()
                resultados_finales.append(item_procesado)
                
                completados += 1
                progreso = int((completados / total_enlaces) * 100)
                barra.progress(progreso)
                texto_estado.text(f"Verificando: {completados} de {total_enlaces} enlaces...")

        # 3. RESULTADOS
        barra.progress(100)
        texto_estado.success("¡Proceso finalizado!")
        
        if resultados_finales:
            df = pd.DataFrame(resultados_finales)
            
            # Métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Enlaces", len(df))
            c2.metric("Activos", len(df[df['Estado'] == "✅ ACTIVO"]))
            errores = len(df[df['Estado'].str.contains("ROTO|ERROR")])
            c3.metric("Con Problemas", errores, delta_color="inverse")
            
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Reporte Rápido",
                data=csv,
                file_name="reporte_fast_doctorado.csv",
                mime="text/csv",
            )
        else:
            st.warning("No se encontraron enlaces en el archivo.")

# --- PIE DE PÁGINA ---
st.write("---")
st.markdown("##### 🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
