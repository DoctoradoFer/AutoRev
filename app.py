import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Verificador de Transparencia", page_icon="🔍", layout="wide")

# ==========================================
# 🔐 SISTEMA DE SEGURIDAD (MÉTODO ST.STOP)
# ==========================================

# 1. Definimos la contraseña correcta
CONTRASENA_SECRETA = "Fernando2026"

# 2. Inicializamos el estado si no existe
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

# 3. Función para verificar cuando dan Enter
def verificar_input():
    if st.session_state["input_pass"] == CONTRASENA_SECRETA:
        st.session_state.password_correct = True
        del st.session_state["input_pass"] # Borramos la clave del campo por seguridad
    else:
        st.session_state.password_correct = False

# 4. EL GUARDIÁN: Si no está logueado, muestra el input y DETIENE EL CÓDIGO
if not st.session_state.password_correct:
    st.markdown("### 🔒 Acceso Restringido")
    st.markdown("Esta herramienta forma parte de una investigación de doctorado y su acceso es privado.")
    st.text_input(
        "Ingresa la contraseña para continuar:", 
        type="password", 
        key="input_pass", 
        on_change=verificar_input
    )
    st.error("⛔ Ingresa la clave y presiona Enter.")
    st.stop()  # <--- ¡AQUÍ ESTÁ LA MAGIA! Esto impide que se cargue lo de abajo.

# ==========================================
# 🚀 APLICACIÓN PRINCIPAL (Solo carga si pasó el st.stop de arriba)
# ==========================================

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
    st.write("---")
    if st.button("Cerrar Sesión / Bloquear"):
        st.session_state.password_correct = False
        st.rerun()

# --- TÍTULO ---
st.title("Verificador de Hipervínculos en formatos de obligaciones de transparencia")
st.markdown("""
Esta herramienta analiza tus formatos de transparencia (Excel), extrae los enlaces
y verifica si están **ACTIVOS** o **ROTOS**.
""")

# --- FUNCIONES DE LÓGICA ---
def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(
        total=3, read=3, connect=3, backoff_factor=1, 
        status_forcelist=[500, 502, 503, 504, 429]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def verificar_un_enlace(datos_enlace):
    url = datos_enlace['URL Original']
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    session = crear_sesion_segura()
    
    try:
        response = session.head(url, headers=headers, allow_redirects=True, timeout=10)
        if response.status_code == 405:
            response = session.get(url, headers=headers, allow_redirects=True, timeout=10, stream=True)
        
        if response.status_code == 200:
            datos_enlace['Estado'] = "✅ ACTIVO"
        elif response.status_code == 404:
            datos_enlace['Estado'] = "❌ ROTO (404)"
        elif response.status_code == 403:
            datos_enlace['Estado'] = "🔒 ACCESO DENEGADO (403)"
        else:
            datos_enlace['Estado'] = f"⚠️ ESTADO {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        datos_enlace['Estado'] = "💀 ERROR DE CONEXIÓN"
    except requests.exceptions.Timeout:
        datos_enlace['Estado'] = "⏳ TIMEOUT"
    except Exception:
        datos_enlace['Estado'] = "⚠️ ERROR DESCONOCIDO"
    finally:
        session.close()
    
    return datos_enlace

# --- INTERFAZ DE CARGA ---
archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado.")
    
    if st.button("Iniciar Verificación (Modo Robusto)"):
        st.write("📂 Escaneando archivo...")
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
        
        if total_enlaces == 0:
            st.warning("No se encontraron enlaces.")
        else:
            st.info(f"Se encontraron {total_enlaces} enlaces. Verificando...")
            
            resultados_finales = []
            barra = st.progress(0)
            texto_estado = st.empty()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(verificar_un_enlace, item): item for item in lista_cruda}
                
                completados = 0
                for future in concurrent.futures.as_completed(futures):
                    item_procesado = future.result()
                    resultados_finales.append(item_procesado)
                    completados += 1
                    
                    if total_enlaces > 0:
                        progreso = int((completados / total_enlaces) * 100)
                        barra.progress(min(progreso, 100))
                    
                    if completados % 5 == 0:
                        texto_estado.text(f"Verificando: {completados} de {total_enlaces} enlaces...")

            barra.progress(100)
            texto_estado.success("¡Finalizado!")
            
            if resultados_finales:
                df = pd.DataFrame(resultados_finales)
                c1, c2, c3 = st.columns(3)
                c1.metric("Total", len(df))
                c2.metric("Activos", len(df[df['Estado'] == "✅ ACTIVO"]))
                errores = len(df[~df['Estado'].str.contains("ACTIVO", na=False)])
                c3.metric("Observaciones", errores, delta_color="inverse")
                st.dataframe(df)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Reporte", csv, "reporte_doctorado.csv", "text/csv")

# --- PIE DE PÁGINA ---
st.write("---")
st.markdown("##### 🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
