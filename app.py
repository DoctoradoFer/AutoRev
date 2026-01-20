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

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Laboratorio Automático", page_icon="🤖", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ MODO LABORATORIO (AUTOMÁTICO)")
    st.header("⚙️ Configuración")
    
    # CONTROL DE LOTES AUTOMÁTICO
    st.info("El sistema procesará el archivo en bloques para proteger la memoria.")
    batch_size = st.number_input("Tamaño del Bloque (Registros por ronda):", min_value=100, max_value=2000, value=1000, step=100)
    
    st.write("---")
    act_auditoria = st.checkbox("🛠️ Auditar Formatos", value=True)
    act_busqueda = st.checkbox("🕵️‍♂️ Buscar Contenido", value=True)
    
    if act_busqueda:
        texto_busqueda = st.text_area("Palabras a buscar:", value="puente, contrato, licitacion")
        lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    else:
        lista_palabras = []

    st.write("---")
    num_robots = st.number_input("🤖 Robots Simultáneos", min_value=1, max_value=8, value=4)
    modo_sigilo = st.checkbox("🐢 Pausa Sigilo", value=False)
    
    if st.button("🗑️ Reiniciar Auditoría (Borrar datos)"):
        if os.path.exists("resultados_acumulados.csv"):
            os.remove("resultados_acumulados.csv")
            st.success("Memoria borrada. Listo para empezar de cero.")
            time.sleep(1)
            st.rerun()

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

# --- 4. LÓGICA TÉCNICA ---
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
        
        if any(f in ext or f in content_type for f in ['xml', 'json', 'rdf', 'csv']):
            calidad = f"✅ Formato Abierto ({ext.upper()})"
            es_legible = True 
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
    
    res = {
        "Hoja": datos["Hoja"], "Celda": datos["Celda"], "URL Original": url,
        "Estado": "Desconocido", "Código": 0, "Tipo": "Pendiente",
        "Formato": "Off", "Contenido": "Off"
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

        res['Código'] = response.status_code
        if response.status_code == 200:
            res['Estado'] = "✅ ACTIVO"
            res['Tipo'] = "Accesible"
            if necesita_descarga:
                cal, hal = auditar_archivo(response, url, act_busqueda, palabras)
                if act_auditoria: res['Formato'] = cal
                if act_busqueda: res['Contenido'] = hal
        elif response.status_code == 404:
            res['Estado'] = "❌ ROTO"
            res['Tipo'] = "Inaccesible"
        else:
            res['Estado'] = f"⚠️ ({response.status_code})"
            res['Tipo'] = "Error"
    except:
        res['Estado'] = "💀 ERROR"
        res['Tipo'] = "Fallo"
    finally:
        if session: session.close()
        del session
        
    return res

# --- 5. INTERFAZ PRINCIPAL ---
st.title("🤖 Laboratorio: Procesamiento Automático por Lotes")
st.markdown("El sistema dividirá el archivo y procesará bloque por bloque automáticamente para proteger la memoria.")

archivo_subido = st.file_uploader("Carga Excel (.xlsx)", type=["xlsx"])
archivo_temp = "resultados_acumulados.csv"

# Mostrar avance si existe
if os.path.exists(archivo_temp):
    df_previo = pd.read_csv(archivo_temp)
    st.info(f"📂 Archivo de respaldo detectado con {len(df_previo)} registros procesados.")
    if st.button("📥 Descargar Avance Actual"):
        # Generar CSV string para descarga
        csv = df_previo.to_csv(index=False).encode('utf-8')
        st.download_button("Guardar CSV", csv, "avance_actual.csv")

if archivo_subido and st.button("🚀 Iniciar Ciclo Automático"):
    # 1. Crear el CSV vacío si no existe
    if not os.path.exists(archivo_temp):
        with open(archivo_temp, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Hoja", "Celda", "URL Original", "Estado", "Código", "Tipo", "Formato", "Contenido"])
            
    # 2. Leer Excel Completo
    wb = load_workbook(archivo_subido, data_only=True, read_only=False)
    lista_total = []
    st.write("⚙️ Analizando estructura del archivo...")
    for hoja in wb.sheetnames:
        ws = wb[hoja]
        for row in ws.iter_rows():
            for cell in row:
                url = None
                if cell.hyperlink: url = cell.hyperlink.target
                elif isinstance(cell.value, str) and str(cell.value).startswith(('http', 'https')): url = cell.value
                
                if url:
                    lista_total.append({
                        "Hoja": hoja, "Celda": cell.coordinate, "URL Original": url,
                        "Activar Auditoría": act_auditoria, "Activar Búsqueda": act_busqueda,
                        "Palabras Clave": lista_palabras, "Sigilo": modo_sigilo
                    })
    wb.close()
    del wb
    gc.collect() # Limpieza inicial
    
    total_enlaces = len(lista_total)
    st.success(f"📋 Total detectado: {total_enlaces} enlaces.")
    
    # 3. Calcular qué falta por hacer
    procesados_count = 0
    if os.path.exists(archivo_temp):
        # Contamos cuántas líneas tiene el CSV (restando encabezado)
        with open(archivo_temp, 'r', encoding='utf-8') as f:
            procesados_count = sum(1 for row in f) - 1
            if procesados_count < 0: procesados_count = 0
            
    st.write(f"📊 Ya procesados: {procesados_count}. Faltan: {total_enlaces - procesados_count}.")
    
    if procesados_count >= total_enlaces:
        st.success("✅ ¡El archivo ya está completamente procesado!")
    else:
        # 4. CICLO DE LOTES AUTOMÁTICO
        lista_pendiente = lista_total[procesados_count:] # Solo lo que falta
        total_pendiente = len(lista_pendiente)
        
        # Dividimos en chunks
        chunks = [lista_pendiente[i:i + batch_size] for i in range(0, total_pendiente, batch_size)]
        
        barra_general = st.progress(0)
        estado_general = st.empty()
        
        # Iteramos sobre los lotes
        for i, chunk in enumerate(chunks):
            lote_num = i + 1
            total_lotes = len(chunks)
            estado_general.markdown(f"### 🔄 Procesando Lote {lote_num} de {total_lotes} ({len(chunk)} enlaces)...")
            
            # --- PROCESAMIENTO DEL LOTE ---
            with open(archivo_temp, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["Hoja", "Celda", "URL Original", "Estado", "Código", "Tipo", "Formato", "Contenido"])
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_robots) as executor:
                    futures = {executor.submit(procesar_enlace, item): item for item in chunk}
                    
                    completados_lote = 0
                    barra_lote = st.progress(0)
                    
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        writer.writerow(res)
                        
                        completados_lote += 1
                        barra_lote.progress(int((completados_lote/len(chunk))*100))
                
                # Forzamos escritura en disco al terminar el lote
                f.flush()
            
            # --- LIMPIEZA DE MEMORIA ---
            del futures
            gc.collect() # ¡Limpieza profunda!
            st.toast(f"✅ Lote {lote_num} guardado y memoria limpia.")
            
            # Actualizar barra general
            progreso_general = int(((i + 1) / total_lotes) * 100)
            barra_general.progress(min(progreso_general, 100))
            
        estado_general.success("🎉 ¡Proceso Completo!")
        
        # Mostrar resultado final
        df_final = pd.read_csv(archivo_temp)
        st.dataframe(df_final)
        st.download_button("📥 Descargar Reporte Final Completo", df_final.to_csv(index=False).encode('utf-8'), "auditoria_final.csv")
