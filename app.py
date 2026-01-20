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
import gc
import os
import csv

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Laboratorio Streaming", page_icon="💾", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ MODO LABORATORIO (STREAMING)")
    st.header("🎛️ Panel de Control")
    
    act_auditoria = st.checkbox("🛠️ Auditar Formatos y Calidad", value=True)
    act_busqueda = st.checkbox("🕵️‍♂️ Buscar Contenido", value=True)
    
    if act_busqueda:
        texto_busqueda = st.text_area("Palabras a buscar:", value="puente, contrato, licitacion")
        lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    else:
        lista_palabras = []

    st.write("---")
    st.header("⚙️ Rendimiento")
    num_robots = st.number_input("🤖 Robots (Hilos)", min_value=1, max_value=8, value=4)
    modo_sigilo = st.checkbox("🐢 Pausa de Sigilo", value=False)
    
    if st.button("🗑️ Borrar Temporales"):
        if os.path.exists("resultados_parciales.csv"):
            os.remove("resultados_parciales.csv")
            st.success("Temporales borrados.")

    st.write("---")
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

# --- 4. FUNCIONES DE LÓGICA ---
def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
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
        if any(f in ext or f in content_type for f in ['xml', 'json', 'rdf', 'csv']):
            calidad = f"✅ Formato Abierto ({ext.upper()})"
            es_legible = True 
        # 2. PDF
        elif 'pdf' in ext or 'application/pdf' in content_type:
            try:
                with io.BytesIO(response.content) as f:
                    reader = PdfReader(f)
                    limit = min(2, len(reader.pages)) 
                    for i in range(limit):
                        page_text = reader.pages[i].extract_text()
                        if page_text: texto_extraido += page_text + " "
                if len(texto_extraido.strip()) > 5:
                    calidad = "✅ PDF Texto (Abierto)"
                    es_legible = True
                else:
                    calidad = "⚠️ PDF Imagen (Requiere OCR)"
            except:
                calidad = "❌ PDF Dañado"
        # 3. HTML
        elif 'html' in ext or 'text/html' in content_type:
            try:
                soup = BeautifulSoup(response.content, 'html.parser')
                texto_extraido = soup.get_text()[:5000]
                calidad = "✅ Sitio Web (HTML)"
                es_legible = True
            except:
                calidad = "⚠️ HTML con errores"
        else:
            calidad = f"⚠️ Formato No Estándar ({ext.upper()})"

        if realizar_busqueda:
            lista_hallazgos = []
            if es_legible and texto_extraido:
                texto_norm = texto_extraido.lower()
                for palabra in palabras_clave:
                    if palabra in texto_norm: lista_hallazgos.append(palabra.upper())
                hallazgos = f"✅ ENCONTRADO: {', '.join(lista_hallazgos)}" if lista_hallazgos else "Sin coincidencias"
            elif not es_legible and "PDF Imagen" in calidad:
                hallazgos = "❌ Imposible leer (Es imagen)"
            else:
                hallazgos = "No legible / Sin texto"
    except:
        calidad = "Error Procesando"
    return calidad, hallazgos

def procesar_enlace(datos):
    if datos['Sigilo']: time.sleep(random.uniform(0.5, 1.5))
    url = datos['URL Original']
    act_auditoria = datos['Activar Auditoría']
    act_busqueda = datos['Activar Búsqueda']
    palabras = datos['Palabras Clave']
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    resultado = {
        "Hoja": datos["Hoja"],
        "Celda": datos["Celda"],
        "URL Original": url,
        "Estado": "Desconocido",
        "Código": 0,
        "Tipo": "Pendiente",
        "Formato": "Off",
        "Contenido": "Off"
    }
    
    session = None
    try:
        session = crear_sesion_segura()
        necesita_descarga = act_auditoria or act_busqueda
        if necesita_descarga:
            response = session.get(url, headers=headers, timeout=10, stream=False)
        else:
            response = session.head(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code == 405:
                response = session.get(url, headers=headers, timeout=5, stream=True)

        resultado['Código'] = response.status_code
        if response.status_code == 200:
            resultado['Estado'] = "✅ ACTIVO"
            resultado['Tipo'] = "Accesible"
            if necesita_descarga:
                res_calidad, res_hallazgos = auditar_archivo(response, url, act_busqueda, palabras)
                if act_auditoria: resultado['Formato'] = res_calidad
                if act_busqueda: resultado['Contenido'] = res_hallazgos
        elif response.status_code == 404:
            resultado['Estado'] = "❌ ROTO"
            resultado['Tipo'] = "Inaccesible"
        else:
            resultado['Estado'] = f"⚠️ ({response.status_code})"
            resultado['Tipo'] = "Error"
    except:
        resultado['Estado'] = "💀 ERROR"
        resultado['Tipo'] = "Fallo"
    finally:
        if session: session.close()
        del session
        gc.collect()
        
    return resultado

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💾 Laboratorio: Auditoría con Autoguardado")
st.markdown("Los resultados se guardan en un archivo temporal en tiempo real para evitar pérdidas por reinicio.")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])

# Verificación de archivo temporal existente
archivo_temp = "resultados_parciales.csv"
if os.path.exists(archivo_temp):
    st.info("📂 Se encontró un archivo de resultados previos.")
    df_previo = pd.read_csv(archivo_temp)
    st.write(f"Registros recuperados: {len(df_previo)}")
    st.dataframe(df_previo.tail(3))
    st.download_button("Descargar lo que llevamos", df_previo.to_csv(index=False).encode('utf-8'), "avance_recuperado.csv")

if archivo_subido and st.button("🚀 Iniciar / Continuar Proceso"):
    # Inicializar CSV si no existe
    if not os.path.exists(archivo_temp):
        with open(archivo_temp, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Hoja", "Celda", "URL Original", "Estado", "Código", "Tipo", "Formato", "Contenido"])

    # Cargar Excel (Solo lectura para ahorrar RAM)
    wb = load_workbook(archivo_subido, data_only=True, read_only=False)
    lista_trabajo = []
    
    st.write("⚙️ Leyendo Excel...")
    for hoja in wb.sheetnames:
        ws = wb[hoja]
        for row in ws.iter_rows():
            for cell in row:
                url = None
                if cell.hyperlink: url = cell.hyperlink.target
                elif isinstance(cell.value, str) and str(cell.value).startswith(('http', 'https')): url = cell.value
                
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
    wb.close()
    del wb
    gc.collect()

    total = len(lista_trabajo)
    st.success(f"Matriz cargada: {total} enlaces.")
    
    # Barra de progreso
    barra = st.progress(0)
    estado = st.empty()
    
    # EJECUCIÓN
    completados = 0
    with open(archivo_temp, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Hoja", "Celda", "URL Original", "Estado", "Código", "Tipo", "Formato", "Contenido"])
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_robots) as executor:
            futures = {executor.submit(procesar_enlace, item): item for item in lista_trabajo}
            
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                
                # Escribimos AL INSTANTE en el disco
                writer.writerow(res)
                # Forzamos que se guarde en disco ya
                f.flush() 
                
                completados += 1
                if completados % 10 == 0:
                    progreso = int((completados/total)*100)
                    barra.progress(min(progreso, 100))
                    estado.text(f"Guardando {completados}/{total} en disco...")
                    
                # Limpieza de memoria cada 50 items
                if completados % 50 == 0:
                    gc.collect()

    barra.progress(100)
    estado.success("✅ Proceso Finalizado y Guardado")
    
    # Cargar resultado final para mostrar
    df_final = pd.read_csv(archivo_temp)
    st.dataframe(df_final)
    st.download_button("Descargar CSV Final", df_final.to_csv(index=False).encode('utf-8'), "auditoria_completa.csv")
