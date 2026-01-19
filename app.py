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
import time
import random

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Laboratorio de Auditoría", page_icon="🧪", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ MODO LABORATORIO (PRUEBAS)")
    st.header("🔍 Configuración de Búsqueda")
    
    st.info("ℹ️ Escribe palabras para buscar DENTRO del contenido (PDFs/Webs).")
    texto_busqueda = st.text_area("Palabras a buscar:", value="puente, contrato, licitacion")
    lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    
    st.write("---")
    usar_lectura_profunda = st.checkbox("📖 Activar Lectura de Contenido", value=True, help="Descarga y lee los archivos para buscar las palabras clave.")
    
    st.write("---")
    st.caption("🚀 CONTROL DE VELOCIDAD")
    # Por defecto está DESACTIVADO (False) para que use los 8 robots (Velocidad Máxima)
    modo_lento = st.checkbox("Activar Modo Sigilo (Anti-bloqueo)", value=False, help="Actívalo solo si el servidor te bloquea. Reduce la velocidad a 2 robots.")

    st.write("---")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
    
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.usuario_valido = False
        st.rerun()

# --- 3. SEGURIDAD ---
if "usuario_valido" not in st.session_state:
    st.session_state.usuario_valido = False

if not st.session_state.usuario_valido:
    st.markdown("# 🔒 Acceso Privado - LABORATORIO")
    clave = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if clave == "Fernando2026":
            st.session_state.usuario_valido = True
            st.rerun()
        else:
            st.error("⛔ Incorrecto")
    st.stop()

# --- 4. LÓGICA DE VERIFICACIÓN ---
def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retry))
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session

def analizar_contenido(response, extension, palabras_clave):
    texto_extraido = ""
    hallazgos = []
    try:
        # 1. Si es PDF
        if "pdf" in extension or "application/pdf" in response.headers.get("Content-Type", ""):
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            # Leemos las primeras 5 páginas para optimizar
            limit = min(5, len(reader.pages)) 
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
        return "Leído, sin coincidencias."

def procesar_enlace(datos):
    # Si el modo sigilo está activo, descansa un poco. Si no, va a tope.
    if datos['Modo Sigilo']:
        time.sleep(random.uniform(1.0, 3.0))
    
    url = datos['URL Original']
    palabras = datos['Palabras Clave']
    usar_profundo = datos['Usar Profundo']
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    session = crear_sesion_segura()
    datos['Estado'] = "Desconocido"
    datos['Rastreador'] = "No analizado"
    
    try:
        if usar_profundo:
            # GET para descargar
            response = session.get(url, headers=headers, timeout=15, stream=False)
        else:
            # HEAD para solo verificar (más rápido)
            response = session.head(url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 405:
                response = session.get(url, headers=headers, timeout=10, stream=True)

        datos['Código'] = response.status_code
        
        if response.status_code == 200:
            datos['Estado'] = "✅ ACTIVO"
            datos['Tipo'] = "Accesible"
            
            # Lógica de Lectura Profunda
            if usar_profundo:
                content_type = response.headers.get('Content-Type', '').lower()
                extension = url.split('.')[-1].lower()
                
                if 'pdf' in content_type or 'pdf' in extension or 'html' in content_type:
                    resultado = analizar_contenido(response, extension, palabras)
                    datos['Rastreador'] = resultado
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
            
    except Exception:
        datos['Estado'] = "💀 ERROR"
        datos['Tipo'] = "Fallo"
        datos['Rastreador'] = "Fallo conexión"
    finally:
        session.close()
    return datos

# --- 5. INTERFAZ PRINCIPAL (ENCABEZADO ACTUALIZADO) ---

st.title("🧪 Laboratorio de Auditoría: Enlaces, Técnica y Contenido")

st.markdown("""
**Herramienta integral para la verificación de obligaciones de transparencia.**
Esta aplicación realiza tres funciones críticas:
1.  🔗 **Verificación de Hipervínculos:** Detecta enlaces rotos, caídos o inexistentes.
2.  ⚙️ **Validación Técnica:** Confirma que los archivos cumplan con los requerimientos de disponibilidad del servidor.
3.  🕵️‍♂️ **Búsqueda Profunda:** Analiza y busca información específica **DENTRO** del contenido de los archivos (PDFs y Sitios Web).
""")

st.info("Sube tu matriz de información en Excel para comenzar el análisis automatizado.")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])

if archivo_subido and st.button("🚀 Iniciar Auditoría Completa"):
    wb = load_workbook(archivo_subido, data_only=True)
    lista_trabajo = []
    
    st.write("⚙️ Preparando matriz de datos...")
    
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
                        "Usar Profundo": usar_lectura_profunda,
                        "Modo Sigilo": modo_lento
                    })
    
    total = len(lista_trabajo)
    if total == 0:
        st.warning("No se encontraron enlaces en el archivo.")
    else:
        # Configuración de Robots:
        # Si Modo Sigilo es False (Defecto) -> Usa 8 Robots.
        # Si Modo Sigilo es True -> Usa 2 Robots.
        workers = 2 if modo_lento else 8
        
        if modo_lento:
            st.info(f"🐢 MODO SIGILO: Analizando {total} documentos con precaución (2 robots)...")
        else:
            st.success(f"🚀 MODO TURBO: Analizando {total} documentos a máxima potencia (8 robots)...")
        
        barra = st.progress(0)
        estado = st.empty()
        resultados = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(procesar_enlace, item): item for item in lista_trabajo}
            completados = 0
            for future in concurrent.futures.as_completed(futures):
                resultados.append(future.result())
                completados += 1
                barra.progress(int((completados/total)*100))
                estado.text(f"Procesando: {completados} de {total}...")
        
        barra.progress(100)
        estado.success("✅ Auditoría Finalizada")
        df = pd.DataFrame(resultados)
        
        # --- RESULTADOS ---
        tab1, tab2, tab3 = st.tabs(["📄 Datos Detallados", "📡 Hallazgos de Contenido", "📊 Tablero Gráfico"])
        
        with tab1:
            st.dataframe(df)
            st.download_button("Descargar Reporte CSV", df.to_csv(index=False).encode('utf-8'), "analisis_lab.csv")
        
        with tab2:
            st.subheader("Resultados de la Búsqueda Profunda")
            encontrados = df[df['Rastreador'].str.contains("ENCONTRADO", na=False)]
            st.metric("Documentos con coincidencias", len(encontrados))
            if not encontrados.empty:
                st.dataframe(encontrados)
            else:
                st.info("No se encontraron las palabras clave dentro de los documentos legibles.")
                
        with tab3:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Índice Global")
                conteo = df['Tipo'].value_counts()
                fig1, ax1 = plt.subplots()
                ax1.pie(conteo, labels=conteo.index, autopct='%1.1f%%', startangle=90, colors=['#66b3ff', '#ff9999', '#ffcc99'])
                ax1.axis('equal')
                st.pyplot(fig1)
            with c2:
                st.markdown("#### Estado Técnico")
                df_err = df[df['Tipo'] != "Accesible"]
                if not df_err.empty:
                    st.bar_chart(df_err['Estado'].value_counts())
            
            st.markdown("#### Mapa de Calor (Hojas)")
            pivot = pd.crosstab(df['Hoja'], df['Tipo'])
            st.dataframe(pivot.style.background_gradient(cmap="Reds"))
