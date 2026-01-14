import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import matplotlib.pyplot as plt
import io
from pypdf import PdfReader
from bs4 import BeautifulSoup

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Verificador - MODO PRUEBAS", page_icon="🧪", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ MODO LABORATORIO: LECTURA PROFUNDA")
    st.header("🔍 Configuración del Rastreador")
    
    st.info("ℹ️ Escribe palabras para buscar DENTRO del contenido de los documentos (PDFs, HTML).")
    texto_busqueda = st.text_area("Palabras a buscar (separadas por coma):", value="puente, contrato, licitacion")
    lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    
    st.write("---")
    # Switch para activar/desactivar la lectura profunda (por velocidad)
    usar_lectura_profunda = st.checkbox("📖 Activar Lectura de Contenido", value=True, help="Si se activa, el sistema descargará los PDFs y buscará las palabras dentro. Es más lento pero más efectivo.")
    
    st.write("---")
    st.markdown("### Mtro. Fernando Gamez Reyes")
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.usuario_valido = False
        st.rerun()

# --- 3. SEGURIDAD ---
if "usuario_valido" not in st.session_state:
    st.session_state.usuario_valido = False

if not st.session_state.usuario_valido:
    st.markdown("# 🔒 Acceso Privado")
    clave = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if clave == "Fernando2026":
            st.session_state.usuario_valido = True
            st.rerun()
        else:
            st.error("⛔ Incorrecto")
    st.stop()

# --- 4. LÓGICA DE LECTURA PROFUNDA ---

def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retry))
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session

def analizar_contenido(response, extension, palabras_clave):
    """Descarga y lee el contenido buscando palabras clave."""
    texto_extraido = ""
    hallazgos = []
    
    try:
        # 1. Si es PDF
        if "pdf" in extension or "application/pdf" in response.headers.get("Content-Type", ""):
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            # Leemos solo las primeras 5 páginas para no saturar memoria
            num_paginas = len(reader.pages)
            limit = min(5, num_paginas) 
            for i in range(limit):
                texto_extraido += reader.pages[i].extract_text() + " "
        
        # 2. Si es Web (HTML)
        elif "html" in extension or "text/html" in response.headers.get("Content-Type", ""):
            soup = BeautifulSoup(response.content, 'html.parser')
            texto_extraido = soup.get_text()
            
        # 3. BÚSQUEDA
        texto_extraido = texto_extraido.lower()
        for palabra in palabras_clave:
            if palabra in texto_extraido:
                hallazgos.append(palabra.upper())
                
    except Exception as e:
        return f"Error leyendo: {str(e)}"

    if hallazgos:
        return f"✅ ENCONTRADO EN DOC: {', '.join(hallazgos)}"
    else:
        return "Contenido leido, sin coincidencias."

def procesar_enlace(datos):
    url = datos['URL Original']
    palabras = datos['Palabras Clave']
    usar_profundo = datos['Usar Profundo']
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = crear_sesion_segura()
    
    datos['Estado'] = "Desconocido"
    datos['Rastreador'] = "No analizado"
    
    try:
        # Primero intentamos HEAD para ver si existe (rápido)
        if usar_profundo:
             # Si vamos a leer, necesitamos GET directo
            response = session.get(url, headers=headers, timeout=10, stream=False)
        else:
            response = session.head(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code == 405:
                response = session.get(url, headers=headers, timeout=5, stream=True)

        datos['Código'] = response.status_code
        
        if response.status_code == 200:
            datos['Estado'] = "✅ ACTIVO"
            datos['Tipo'] = "Accesible"
            
            # --- AQUÍ OCURRE LA MAGIA DE LA LECTURA ---
            if usar_profundo:
                content_type = response.headers.get('Content-Type', '').lower()
                extension = url.split('.')[-1].lower()
                # Analizamos si es PDF o HTML
                if 'pdf' in content_type or 'pdf' in extension or 'html' in content_type:
                    resultado_lectura = analizar_contenido(response, extension, palabras)
                    datos['Rastreador'] = resultado_lectura
                else:
                    datos['Rastreador'] = "Formato no legible (zip/img)"
            else:
                datos['Rastreador'] = "Lectura desactivada"
                
        elif response.status_code == 404:
            datos['Estado'] = "❌ ROTO"
            datos['Tipo'] = "Inaccesible"
        else:
            datos['Estado'] = f"⚠️ ({response.status_code})"
            datos['Tipo'] = "Error"
            
    except Exception as e:
        datos['Estado'] = "💀 ERROR"
        datos['Tipo'] = "Fallo"
        datos['Rastreador'] = "No se pudo conectar"
    finally:
        session.close()
        
    return datos

# --- 5. INTERFAZ ---

st.title("🧪 Laboratorio: Lector de Contenido Profundo")
st.markdown("""
Esta herramienta **descarga y lee** el contenido de los enlaces (PDFs y Webs) para encontrar información oculta 
que no aparece en el nombre del archivo.
""")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])

if archivo_subido and st.button("🚀 Iniciar Análisis Profundo"):
    st.write("⚙️ Procesando... Esto puede tardar más de lo normal porque estamos leyendo los documentos.")
    
    wb = load_workbook(archivo_subido, data_only=True) # data_only=True ayuda a veces con fórmulas
    lista_trabajo = []
    
    for hoja in wb.sheetnames:
        ws = wb[hoja]
        for row in ws.iter_rows():
            for cell in row:
                url = None
                if cell.hyperlink:
                    url = cell.hyperlink.target
                elif isinstance(cell.value, str) and str(cell.value).startswith(('http', 'https')):
                    url = cell.value
                
                if url:
                    lista_trabajo.append({
                        "Hoja": hoja,
                        "Celda": cell.coordinate,
                        "URL Original": url,
                        "Palabras Clave": lista_palabras,
                        "Usar Profundo": usar_lectura_profunda
                    })
    
    total = len(lista_trabajo)
    if total == 0:
        st.warning("No se encontraron enlaces.")
    else:
        barra = st.progress(0)
        estado = st.empty()
        resultados = []
        
        # Reducimos workers a 4 para no saturar memoria con los PDFs
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(procesar_enlace, item): item for item in lista_trabajo}
            completados = 0
            for future in concurrent.futures.as_completed(futures):
                resultados.append(future.result())
                completados += 1
                barra.progress(int((completados/total)*100))
                estado.text(f"Analizando documento {completados} de {total}...")
        
        barra.progress(100)
        estado.success("✅ Análisis Profundo Terminado")
        
        df = pd.DataFrame(resultados)
        
        tab1, tab2 = st.tabs(["📄 Resultados", "📡 Hallazgos en Documentos"])
        
        with tab1:
            st.dataframe(df)
            st.download_button("Descargar CSV", df.to_csv(index=False).encode('utf-8'), "analisis_profundo.csv")
            
        with tab2:
            st.subheader("Documentos que contienen las palabras buscadas")
            # Filtramos donde el rastreador encontró algo
            encontrados = df[df['Rastreador'].str.contains("ENCONTRADO", na=False)]
            st.metric("Documentos Positivos", len(encontrados))
            if not encontrados.empty:
                st.dataframe(encontrados)
            else:
                st.info("No se encontraron las palabras dentro de los documentos legibles.")
