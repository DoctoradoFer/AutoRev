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

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Verificador - MODO PRUEBAS", page_icon="🐢", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ MODO LABORATORIO: LECTURA PROFUNDA")
    st.header("🔍 Configuración del Rastreador")
    
    st.info("ℹ️ Escribe palabras para buscar DENTRO del contenido (PDFs/Webs).")
    texto_busqueda = st.text_area("Palabras a buscar:", value="puente, contrato, licitacion")
    lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    
    st.write("---")
    usar_lectura_profunda = st.checkbox("📖 Activar Lectura de Contenido", value=True)
    
    st.write("---")
    st.caption("🐢 CONTROL DE VELOCIDAD")
    # Nota: Por defecto lo dejo desactivado para que uses tus 8 robots, actívalo si te bloquean.
    modo_lento = st.checkbox("Activar Modo Sigilo (Anti-bloqueo)", value=False, help="Si se marca, reduce la velocidad y usa menos robots.")

    st.write("---")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
    
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.usuario_valido = False
        st.rerun()

# --- 3. SEGURIDAD ---
if "usuario_valido" not in st.session_state:
    st.session_state.usuario_valido = False

if not st.session_state.usuario_valido:
    st.markdown("# 🔒 Acceso Privado - LAB")
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
        if "pdf" in extension or "application/pdf" in response.headers.get("Content-Type", ""):
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            limit = min(5, len(reader.pages)) 
            for i in range(limit):
                texto_extraido += reader.pages[i].extract_text() + " "
        elif "html" in extension or "text/html" in response.headers.get("Content-Type", ""):
            soup = BeautifulSoup(response.content, 'html.parser')
            texto_extraido = soup.get_text()
            
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
    # Pausa de Sigilo SOLO si está activado
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
            response = session.get(url, headers=headers, timeout=15, stream=False)
        else:
            response = session.head(url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 405:
                response = session.get(url, headers=headers, timeout=10, stream=True)

        datos['Código'] = response.status_code
        
        if response.status_code == 200:
            datos['Estado'] = "✅ ACTIVO"
            datos['Tipo'] = "Accesible"
            if usar_profundo:
                content_type = response.headers.get('Content-Type', '').lower()
                extension = url.split('.')[-1].lower()
                if 'pdf' in content_type or 'pdf' in extension or 'html' in content_type:
                    resultado = analizar_contenido(response, extension, palabras)
                    datos['Rastreador'] = resultado
                else:
                    datos['Rastreador'] = "Formato no legible"
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

# --- 5. INTERFAZ ---
st.title("🐢 Laboratorio: Lector Profundo (Modo Pruebas)")
st.markdown("Herramienta experimental con análisis de contenido.")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])

if archivo_subido and st.button("🚀 Iniciar Análisis"):
    wb = load_workbook(archivo_subido, data_only=True)
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
                        "Usar Profundo": usar_lectura_profunda,
                        "Modo Sigilo": modo_lento
                    })
    
    total = len(lista_trabajo)
    if total == 0:
        st.warning("No se encontraron enlaces.")
    else:
        # LOGICA DE ROBOTS: Si Sigilo está OFF = 8 Robots. Si ON = 2 Robots.
        workers = 2 if modo_lento else 8
        
        if modo_lento:
            st.info(f"🐢 MODO SIGILO: Analizando {total} docs lentamente (2 robots)...")
        else:
            st.success(f"🚀 MODO TURBO: Analizando {total} docs a máxima velocidad (8 robots)...")
        
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
                estado.text(f"Analizando {completados}/{total}...")
        
        barra.progress(100)
        estado.success("✅ Terminado")
        df = pd.DataFrame(resultados)
        
        tab1, tab2, tab3 = st.tabs(["📄 Datos", "📡 Hallazgos", "📊 Gráficos"])
        
        with tab1:
            st.dataframe(df)
            st.download_button("Descargar CSV", df.to_csv(index=False).encode('utf-8'), "analisis_lab.csv")
        
        with tab2:
            st.subheader("Hallazgos en Documentos")
            encontrados = df[df['Rastreador'].str.contains("ENCONTRADO", na=False)]
            st.metric("Positivos", len(encontrados))
            if not encontrados.empty:
                st.dataframe(encontrados)
            else:
                st.info("Sin coincidencias.")
                
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
                df_err = df[df['Tipo'] != "Accesible"]
                if not df_err.empty:
                    st.bar_chart(df_err['Estado'].value_counts())
            
            st.markdown("#### Mapa de Calor")
            pivot = pd.crosstab(df['Hoja'], df['Tipo'])
            st.dataframe(pivot.style.background_gradient(cmap="Reds"))
