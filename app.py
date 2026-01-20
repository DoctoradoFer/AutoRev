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
import gc  # <--- NUEVO: Recolector de Basura (El camión de la basura de la RAM)

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Laboratorio Modular", page_icon="🛡️", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ MODO LABORATORIO (ESTABILIDAD)")
    
    st.header("🎛️ Panel de Control")
    st.markdown("Selecciona herramientas:")
    
    # --- INTERRUPTORES ---
    act_auditoria = st.checkbox("🛠️ Auditar Formatos y Calidad", value=True)
    act_busqueda = st.checkbox("🕵️‍♂️ Buscar Contenido", value=True)
    
    st.write("---")
    
    if act_busqueda:
        st.info("ℹ️ Configuración de Búsqueda:")
        texto_busqueda = st.text_area("Palabras a buscar:", value="puente, contrato, licitacion")
        lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    else:
        lista_palabras = []

    st.write("---")
    st.caption("🚀 GESTIÓN DE RECURSOS")
    modo_sigilo = st.checkbox("🐢 Modo Sigilo (Anti-bloqueo)", value=False)
    
    # NUEVO: Control de Lotes para evitar crash
    st.caption("📦 TAMAÑO DEL LOTE (Memoria)")
    batch_size = st.slider("Enlaces por lote (Bajar si se reinicia):", min_value=10, max_value=100, value=50)

    st.write("---")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
    
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

# --- 4. LÓGICA DEL SISTEMA ---
def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retry))
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session

def auditar_archivo(response, url, realizar_busqueda, palabras_clave):
    calidad = "No solicitado"
    hallazgos = "No solicitado"
    texto_extraido = ""
    
    try:
        headers = response.headers
        content_type = headers.get('Content-Type', '').lower()
        ext = url.split('.')[-1].lower()
        
        es_legible = False
        
        # 1. Datos Estructurados
        formatos_datos = ['xml', 'json', 'rdf', 'csv']
        if any(f in ext for f in formatos_datos) or any(f in content_type for f in formatos_datos):
            calidad = f"✅ Formato Abierto ({ext.upper()})"
            es_legible = True 
        
        # 2. PDF
        elif 'pdf' in ext or 'application/pdf' in content_type:
            try:
                with io.BytesIO(response.content) as f: # Context manager para liberar memoria rápido
                    reader = PdfReader(f)
                    limit = min(3, len(reader.pages)) 
                    for i in range(limit):
                        page_text = reader.pages[i].extract_text()
                        if page_text:
                            texto_extraido += page_text + " "
                
                if len(texto_extraido.strip()) > 5:
                    calidad = "✅ PDF Texto (Abierto)"
                    es_legible = True
                else:
                    calidad = "⚠️ PDF Imagen (Requiere OCR)"
                    es_legible = False
            except:
                calidad = "❌ PDF Dañado"
                
        # 3. HTML
        elif 'html' in ext or 'text/html' in content_type:
            try:
                soup = BeautifulSoup(response.content, 'html.parser')
                texto_extraido = soup.get_text()
                calidad = "✅ Sitio Web (HTML)"
                es_legible = True
            except:
                calidad = "⚠️ HTML con errores"
        else:
            calidad = f"⚠️ Formato No Estándar ({ext.upper()})"

        # BÚSQUEDA
        if realizar_busqueda:
            lista_hallazgos = []
            if es_legible and texto_extraido:
                texto_norm = texto_extraido.lower()
                for palabra in palabras_clave:
                    if palabra in texto_norm:
                        lista_hallazgos.append(palabra.upper())
                hallazgos = f"✅ ENCONTRADO: {', '.join(lista_hallazgos)}" if lista_hallazgos else "Sin coincidencias"
            elif not es_legible and "PDF Imagen" in calidad:
                hallazgos = "❌ Imposible leer (Es imagen)"
            else:
                hallazgos = "No legible / Sin texto"
                
    except Exception as e:
        calidad = "Error Procesando"
    
    return calidad, hallazgos

def procesar_enlace(datos):
    if datos['Sigilo']:
        time.sleep(random.uniform(0.5, 2.0))
    
    url = datos['URL Original']
    act_auditoria = datos['Activar Auditoría']
    act_busqueda = datos['Activar Búsqueda']
    palabras = datos['Palabras Clave']
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    datos['Estado'] = "Desconocido"
    datos['Formato'] = "Off"
    datos['Contenido'] = "Off"
    
    session = None
    try:
        session = crear_sesion_segura()
        necesita_descarga = act_auditoria or act_busqueda
        
        if necesita_descarga:
            # Stream=False descarga todo a memoria. Peligroso pero necesario para pypdf.
            response = session.get(url, headers=headers, timeout=15, stream=False)
        else:
            response = session.head(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code == 405:
                response = session.get(url, headers=headers, timeout=5, stream=True)

        datos['Código'] = response.status_code
        
        if response.status_code == 200:
            datos['Estado'] = "✅ ACTIVO"
            datos['Tipo'] = "Accesible"
            
            if necesita_descarga:
                res_calidad, res_hallazgos = auditar_archivo(response, url, act_busqueda, palabras)
                if act_auditoria: datos['Formato'] = res_calidad
                if act_busqueda: datos['Contenido'] = res_hallazgos
            
        elif response.status_code == 404:
            datos['Estado'] = "❌ ROTO"
            datos['Tipo'] = "Inaccesible"
        else:
            datos['Estado'] = f"⚠️ ({response.status_code})"
            datos['Tipo'] = "Error"
            
    except Exception:
        datos['Estado'] = "💀 ERROR"
        datos['Tipo'] = "Fallo"
        datos['Formato'] = "Error Conexión"
    finally:
        if session: session.close()
        
    return datos

# --- 5. INTERFAZ PRINCIPAL ---

st.title("🛡️ Laboratorio Estable (Anti-Crash)")
st.markdown("""
**Sistema optimizado para grandes volúmenes de datos.**
Se utiliza procesamiento por lotes para evitar desbordamiento de memoria.
""")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])

if archivo_subido and st.button("🚀 Iniciar Proceso Seguro"):
    wb = load_workbook(archivo_subido, data_only=True)
    lista_trabajo = []
    
    st.write("⚙️ Preparando matriz...")
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
                        "Activar Auditoría": act_auditoria,
                        "Activar Búsqueda": act_busqueda,
                        "Palabras Clave": lista_palabras,
                        "Sigilo": modo_sigilo
                    })
    
    total = len(lista_trabajo)
    if total == 0:
        st.warning("No se encontraron enlaces.")
    else:
        # 1. Ajuste Dinámico de Workers (Seguridad ante todo)
        if modo_sigilo:
            workers = 2
        elif act_busqueda or act_auditoria:
            # Si hay lectura pesada, limitamos workers para proteger RAM
            workers = 4 
            st.info("ℹ️ Modo de Lectura Profunda activo: Se limitan los robots a 4 para proteger la memoria.")
        else:
            workers = 10 # Si es solo check, volamos
        
        # 2. PROCESAMIENTO POR LOTES (La clave anti-reinicio)
        resultados = []
        barra = st.progress(0)
        estado = st.empty()
        
        # Dividimos la lista gigante en trozos pequeños (chunks)
        chunks = [lista_trabajo[i:i + batch_size] for i in range(0, total, batch_size)]
        
        st.write(f"📦 Procesando en {len(chunks)} lotes de {batch_size} archivos para estabilidad...")
        
        completados_global = 0
        
        for i, chunk in enumerate(chunks):
            estado.text(f"⏳ Procesando Lote {i+1}/{len(chunks)}...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(procesar_enlace, item): item for item in chunk}
                for future in concurrent.futures.as_completed(futures):
                    resultados.append(future.result())
                    completados_global += 1
                    progreso = int((completados_global/total)*100)
                    barra.progress(min(progreso, 100))
            
            # --- LIMPIEZA DE MEMORIA ---
            # Al terminar un lote, forzamos la limpieza de RAM
            gc.collect() 
            # ---------------------------

        barra.progress(100)
        estado.success("✅ Proceso Finalizado con Éxito")
        df = pd.DataFrame(resultados)
        
        # --- PESTAÑAS ---
        tabs_titulos = ["📄 Resultados Generales", "📊 Gráficos"]
        if act_auditoria: tabs_titulos.insert(1, "🛠️ Detalles Técnicos")
        if act_busqueda: tabs_titulos.insert(2, "🕵️‍♂️ Hallazgos de Contenido")
            
        tabs = st.tabs(tabs_titulos)
        
        with tabs[0]:
            st.dataframe(df)
            st.download_button("Descargar CSV", df.to_csv(index=False).encode('utf-8'), "auditoria_segura.csv")
            
        idx = 1
        if act_auditoria:
            with tabs[idx]:
                st.subheader("Análisis de Formatos")
                c1, c2 = st.columns(2)
                c1.warning("⚠️ Requieren OCR (Imagen):")
                c1.dataframe(df[df['Formato'].str.contains("Imagen", na=False)])
                c2.error("❌ Formatos No Estándar:")
                c2.dataframe(df[df['Formato'].str.contains("No Estándar", na=False)])
            idx += 1
            
        if act_busqueda:
            with tabs[idx]:
                st.subheader("Coincidencias de Texto")
                encontrados = df[df['Contenido'].str.contains("ENCONTRADO", na=False)]
                st.metric("Documentos Positivos", len(encontrados))
                st.dataframe(encontrados)
            idx += 1
            
        with tabs[idx]:
            c_g1, c_g2 = st.columns(2)
            c_g1.markdown("#### Disponibilidad")
            st.bar_chart(df['Estado'].value_counts())
            if act_auditoria:
                c_g2.markdown("#### Calidad")
                st.bar_chart(df['Formato'].value_counts())
