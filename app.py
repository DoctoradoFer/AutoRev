import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Verificador de Transparencia", page_icon="🔍", layout="wide")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
    st.write("---")
    st.write("Configuración: Modo Seguro (Reintentos activados para evitar bloqueos en archivos masivos).")

# --- TÍTULO ---
st.title("Verificador de Hipervínculos en formatos de obligaciones de transparencia")
st.markdown("""
Esta herramienta analiza tus formatos de transparencia (Excel), extrae los enlaces
y verifica si están **ACTIVOS** o **ROTOS**.
*Nota: Para archivos grandes (+1000 enlaces), el proceso incluye pausas automáticas para evitar falsos negativos.*
""")

# --- FUNCIÓN DE SESIÓN ROBUSTA (NUEVO) ---
def crear_sesion_segura():
    """Crea una sesión que reintenta automáticamente si falla la conexión"""
    session = requests.Session()
    # Configuración de reintentos: 3 intentos totales
    # backoff_factor=1 significa: espera 0.5s, luego 1s, luego 2s entre intentos
    # status_forcelist: reintenta también si el servidor da error 500, 502, 503, 504 o 429 (Too Many Requests)
    retry = Retry(
        total=3, 
        read=3, 
        connect=3, 
        backoff_factor=1, 
        status_forcelist=[500, 502, 503, 504, 429]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# --- FUNCIÓN DE VERIFICACIÓN ---
def verificar_un_enlace(datos_enlace):
    url = datos_enlace['URL Original']
    # User-Agent rotativo o genérico para parecer navegador real
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    session = crear_sesion_segura()
    
    try:
        # Timeout aumentado a 10s para servidores lentos de gobierno
        response = session.head(url, headers=headers, allow_redirects=True, timeout=10)
        
        # Si head falla con 405 (Método no permitido), intentamos GET
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
        datos_enlace['Estado'] = "💀 ERROR DE CONEXIÓN (Posible bloqueo)"
    except requests.exceptions.Timeout:
        datos_enlace['Estado'] = "⏳ TIMEOUT (Servidor muy lento)"
    except Exception as e:
        datos_enlace['Estado'] = "⚠️ ERROR DESCONOCIDO"
    finally:
        session.close()
    
    return datos_enlace

# --- INTERFAZ ---
archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado.")
    
    if st.button("Iniciar Verificación (Modo Robusto)"):
        
        # 1. FASE DE ESCANEO
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
        
        if total_enlaces == 0:
            st.warning("No se encontraron enlaces en el archivo.")
        else:
            st.info(f"Se encontraron {total_enlaces} enlaces. Iniciando verificación segura...")
            
            # 2. FASE DE PROCESAMIENTO PARALELO
            resultados_finales = []
            barra = st.progress(0)
            texto_estado = st.empty()
            
            # REDUCCIÓN DE WORKERS: Bajamos a 5 para no saturar servidores
            # Esto hace que sea un poco más lento pero MUCHO más fiable
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
                    
                    # Actualizamos el texto cada 10 items para no parpadear tanto
                    if completados % 5 == 0:
                        texto_estado.text(f"Verificando: {completados} de {total_enlaces} enlaces...")

            # 3. RESULTADOS
            barra.progress(100)
            texto_estado.success("¡Proceso finalizado!")
            
            if resultados_finales:
                df = pd.DataFrame(resultados_finales)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Enlaces", len(df))
                c2.metric("Activos", len(df[df['Estado'] == "✅ ACTIVO"]))
                # Filtramos cualquier cosa que no sea Activo
                errores = len(df[~df['Estado'].str.contains("ACTIVO", na=False)])
                c3.metric("Con Observaciones", errores, delta_color="inverse")
                
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte Completo",
                    data=csv,
                    file_name="reporte_doctorado_robusto.csv",
                    mime="text/csv",
                )

# --- PIE DE PÁGINA ---
st.write("---")
st.markdown("##### 🎓 App desarrollada dentro del trabajo de doctorado de Fernando.")
