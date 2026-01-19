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
    st.header("🔍 Configuración")
    
    st.info("ℹ️ Búsqueda de Contenido:")
    texto_busqueda = st.text_area("Palabras a buscar (dentro del archivo):", value="puente, contrato, licitacion")
    lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    
    st.write("---")
    st.caption("🚀 VELOCIDAD DE LOS ROBOTS")
    modo_lento = st.checkbox("Activar Modo Sigilo (Anti-bloqueo)", value=False, help="Reduce velocidad a 2 robots si el servidor te bloquea.")

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

# --- 4. LÓGICA DE AUDITORÍA ---
def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retry))
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session

def auditar_archivo(response, url, palabras_clave):
    """
    Analiza formato, calidad (OCR) y busca contenido.
    Retorna: (Calidad, Hallazgos)
    """
    calidad = "Desconocido"
    hallazgos = []
    texto_extraido = ""
    
    headers = response.headers
    content_type = headers.get('Content-Type', '').lower()
    ext = url.split('.')[-1].lower()
    
    # --- A) AUDITORÍA DE FORMATO Y CALIDAD ---
    
    # 1. Formatos de Datos Estructurados (XML, JSON, RDF, CSV)
    formatos_datos = ['xml', 'json', 'rdf', 'csv']
    if any(f in ext for f in formatos_datos) or any(f in content_type for f in formatos_datos):
        calidad = f"✅ Formato Abierto ({ext.upper()})"
        # (Opcional: Podríamos leer texto de aquí también si fuera necesario)
    
    # 2. Análisis de PDF (Abierto vs Escaneado)
    elif 'pdf' in ext or 'application/pdf' in content_type:
        try:
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            # Leemos las primeras 3 páginas para diagnóstico
            limit = min(3, len(reader.pages)) 
            for i in range(limit):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    texto_extraido += page_text + " "
            
            # Diagnóstico de OCR
            if len(texto_extraido.strip()) > 5: # Si hay texto reconocible
                calidad = "✅ PDF Texto (Abierto)"
            else:
                calidad = "⚠️ PDF Imagen (Requiere OCR)" # Archivo válido, pero mala calidad de datos
                
        except Exception:
            calidad = "❌ PDF Dañado/Protegido"
            
    # 3. HTML / Web
    elif 'html' in ext or 'text/html' in content_type:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            texto_extraido = soup.get_text()
            calidad = "✅ Sitio Web (HTML)"
        except:
            calidad = "⚠️ HTML con errores"
            
    # 4. Otros formatos (Word, Excel, Zip, Imagen)
    else:
        calidad = f"⚠️ Formato No Estándar ({ext.upper()})"

    # --- B) BÚSQUEDA DE CONTENIDO (RASTREADOR) ---
    if texto_extraido:
        texto_extraido = texto_extraido.lower()
        for palabra in palabras_clave:
            if palabra in texto_extraido:
                hallazgos.append(palabra.upper())

    res_hallazgos = f"✅ ENCONTRADO: {', '.join(hallazgos)}" if hallazgos else "Sin coincidencias"
    
    return calidad, res_hallazgos

def procesar_enlace(datos):
    if datos['Modo Sigilo']:
        time.sleep(random.uniform(1.0, 3.0))
    
    url = datos['URL Original']
    palabras = datos['Palabras Clave']
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    session = crear_sesion_segura()
    
    datos['Estado'] = "Desconocido"
    datos['Formato/Calidad'] = "No analizado" # Nueva Columna
    datos['Rastreador'] = "No analizado"
    
    try:
        # Siempre hacemos GET para descargar y analizar calidad
        response = session.get(url, headers=headers, timeout=15, stream=False)

        datos['Código'] = response.status_code
        
        if response.status_code == 200:
            datos['Estado'] = "✅ ACTIVO"
            datos['Tipo'] = "Accesible"
            
            # Ejecutamos la auditoría técnica y de contenido
            calidad, hallazgos = auditar_archivo(response, url, palabras)
            datos['Formato/Calidad'] = calidad
            datos['Rastreador'] = hallazgos
            
        elif response.status_code == 404:
            datos['Estado'] = "❌ ROTO"
            datos['Tipo'] = "Inaccesible"
        else:
            datos['Estado'] = f"⚠️ ({response.status_code})"
            datos['Tipo'] = "Error"
            
    except Exception:
        datos['Estado'] = "💀 ERROR"
        datos['Tipo'] = "Fallo"
        datos['Formato/Calidad'] = "Error Conexión"
    finally:
        session.close()
    return datos

# --- 5. INTERFAZ PRINCIPAL ---

st.title("🧪 Laboratorio de Auditoría Técnica y de Contenido")

st.markdown("""
**Sistema Integral de Validación de Transparencia**
1.  **Disponibilidad:** Verifica enlaces rotos (404, 500).
2.  **Calidad de Datos:** Detecta formatos abiertos (XML, CSV, JSON) vs. cerrados.
3.  **Auditoría OCR:** Identifica si los PDFs son legibles o son imágenes escaneadas.
4.  **Contenido:** Busca palabras clave dentro de los documentos.
""")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])

if archivo_subido and st.button("🚀 Iniciar Auditoría Técnica"):
    wb = load_workbook(archivo_subido, data_only=True)
    lista_trabajo = []
    
    st.write("⚙️ Preparando análisis...")
    
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
                        "Modo Sigilo": modo_lento
                    })
    
    total = len(lista_trabajo)
    if total == 0:
        st.warning("No se encontraron enlaces.")
    else:
        workers = 2 if modo_lento else 8
        st.info(f"Analizando {total} documentos con {workers} robots en paralelo...")
        
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
                estado.text(f"Auditando: {completados}/{total}...")
        
        barra.progress(100)
        estado.success("✅ Auditoría Finalizada")
        df = pd.DataFrame(resultados)
        
        # --- PESTAÑAS DE RESULTADOS ---
        tab1, tab2, tab3 = st.tabs(["📄 Resultados Técnicos", "⚠️ Alertas de Formato", "📊 Gráficos"])
        
        with tab1:
            st.dataframe(df)
            st.download_button("Descargar Reporte Completo (CSV)", df.to_csv(index=False).encode('utf-8'), "auditoria_tecnica.csv")
        
        with tab2:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Archivos Escaneados (Sin OCR)")
                # Filtramos los PDFs que dicen "Imagen"
                ocr_pendiente = df[df['Formato/Calidad'].str.contains("Requiere OCR", na=False)]
                st.metric("PDFs que son solo Imagen", len(ocr_pendiente))
                if not ocr_pendiente.empty:
                    st.error("Estos archivos no cumplen con estándares de datos abiertos (son imágenes):")
                    st.dataframe(ocr_pendiente)
                else:
                    st.success("¡Excelente! Todos los PDFs parecen tener texto legible.")
            
            with c2:
                st.subheader("Formatos No Estándar")
                # Filtramos lo que no es PDF ni Web ni Dato Abierto
                no_estandar = df[df['Formato/Calidad'].str.contains("No Estándar", na=False)]
                st.metric("Formatos Propietarios (Docx, etc)", len(no_estandar))
                if not no_estandar.empty:
                    st.warning("Archivos que deberían migrarse a formatos abiertos:")
                    st.dataframe(no_estandar)

        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Calidad de Formatos")
                if not df.empty:
                    conteo_calidad = df['Formato/Calidad'].value_counts()
                    st.bar_chart(conteo_calidad)
            with col2:
                st.markdown("#### Estado de Enlaces")
                conteo_estado = df['Estado'].value_counts()
                st.bar_chart(conteo_estado)
