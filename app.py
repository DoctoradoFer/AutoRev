import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import matplotlib.pyplot as plt
import seaborn as sns 

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Verificador - MODO PRUEBAS", page_icon="🧪", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ ESTÁS EN MODO PRUEBAS (LABORATORIO)")
    st.header("🔍 Configuración del Rastreador")
    
    # --- CONFIGURACIÓN DE BÚSQUEDA ---
    st.info("ℹ️ INSTRUCCIONES: Escribe las palabras que deseas encontrar separadas por una coma.")
    st.caption("Ejemplo: puente, contrato, nomina")
    
    texto_busqueda = st.text_area("Palabras a rastrear:", value="reservado, confidencial, inexistente, prueba, vacio, no aplica")
    # Limpiamos y preparamos las palabras
    lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    
    st.write("---")
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.usuario_valido = False
        st.rerun()

# ==========================================
# 🔐 3. EL BÚNKER (SEGURIDAD)
# ==========================================

if "usuario_valido" not in st.session_state:
    st.session_state.usuario_valido = False

if not st.session_state.usuario_valido:
    st.markdown("# 🔒 Acceso Privado - LABORATORIO")
    st.info("Ingresa la clave autorizada para acceder a la herramienta.")
    clave_ingresada = st.text_input("Contraseña:", type="password")
    if st.button("Entrar al Sistema"):
        if clave_ingresada == "Fernando2026":
            st.session_state.usuario_valido = True
            st.success("¡Acceso Correcto!")
            st.rerun()
        else:
            st.error("⛔ Clave incorrecta.")
    st.stop()

# ==========================================
# 🚀 4. LÓGICA DE VERIFICACIÓN
# ==========================================

def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(
        total=2, read=2, connect=2, backoff_factor=0.5, 
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
        response = session.head(url, headers=headers, allow_redirects=True, timeout=5)
        if response.status_code == 405:
            response = session.get(url, headers=headers, allow_redirects=True, timeout=5, stream=True)
        
        datos_enlace['Código'] = response.status_code
        
        if response.status_code == 200:
            datos_enlace['Estado'] = "✅ ACTIVO (200)"
            datos_enlace['Tipo'] = "Accesible"
        elif response.status_code == 404:
            datos_enlace['Estado'] = "❌ ROTO (404)"
            datos_enlace['Tipo'] = "Inaccesible"
        elif response.status_code == 403:
            datos_enlace['Estado'] = "🔒 PROHIBIDO (403)"
            datos_enlace['Tipo'] = "Bloqueado"
        else:
            datos_enlace['Estado'] = f"⚠️ ALERTA ({response.status_code})"
            datos_enlace['Tipo'] = "Error Técnico"
            
    except requests.exceptions.ConnectionError:
        datos_enlace['Estado'] = "💀 ERROR CONEXIÓN"
        datos_enlace['Tipo'] = "Fallo Red"
        datos_enlace['Código'] = 0
    except requests.exceptions.Timeout:
        datos_enlace['Estado'] = "⏳ TIMEOUT"
        datos_enlace['Tipo'] = "Fallo Red"
        datos_enlace['Código'] = 0
    except Exception:
        datos_enlace['Estado'] = "⚠️ ERROR DESCONOCIDO"
        datos_enlace['Tipo'] = "Error"
        datos_enlace['Código'] = 0
    finally:
        session.close()
    return datos_enlace

# ==========================================
# 📊 5. INTERFAZ PRINCIPAL
# ==========================================

st.title("🧪 Laboratorio: Auditoría y Rastreo de Información")
st.markdown("Herramienta experimental para análisis masivo de obligaciones de transparencia.")

if lista_palabras:
    st.caption(f"📡 El Rastreador está buscando: {', '.join(lista_palabras)}")

archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado.")
    
    if st.button("🚀 Iniciar Análisis"):
        st.write("⚙️ Ejecutando: Extracción + Rastreo de Texto + Verificación de Enlaces...")
        wb = load_workbook(archivo_subido, data_only=False)
        lista_cruda = []
        
        # --- FASE 1: EXTRACCIÓN Y RASTREO ---
        for nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            for row in ws.iter_rows():
                for cell in row:
                    url_encontrada = None
                    # Convertimos a string de forma segura
                    texto_celda = str(cell.value).strip() if cell.value else ""
                    
                    if cell.hyperlink:
                        url_encontrada = cell.hyperlink.target
                    elif isinstance(cell.value, str) and str(cell.value).startswith(('http://', 'https://')):
                        url_encontrada = cell.value
                    
                    if url_encontrada:
                        # Lógica del Rastreador
                        hallazgo = "Normal"
                        # Convertimos todo a minúsculas para comparar
                        texto_para_analizar = (texto_celda + " " + url_encontrada).lower()
                        
                        for palabra in lista_palabras:
                            if palabra in texto_para_analizar:
                                hallazgo = f"🔍 {palabra.upper()}"
                                break
                        
                        lista_cruda.append({
                            "Hoja": nombre_hoja,
                            "Coordenada": cell.coordinate,
                            "Texto Celda": texto_celda,
                            "URL Original": url_encontrada,
                            "Rastreador": hallazgo, # <--- Nombre actualizado
                            "Estado": "Pendiente",
                            "Tipo": "Pendiente",
                            "Código": 0
                        })
        
        total_enlaces = len(lista_cruda)
        
        if total_enlaces == 0:
            st.warning("No se encontraron enlaces en el archivo. (Recuerda: El Rastreador solo busca en celdas con hipervínculos).")
        else:
            # --- FASE 2: VERIFICACIÓN CONCURRENTE ---
            barra = st.progress(0)
            texto_estado = st.empty()
            resultados_finales = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(verificar_un_enlace, item): item for item in lista_cruda}
                completados = 0
                for future in concurrent.futures.as_completed(futures):
                    resultados_finales.append(future.result())
                    completados += 1
                    progreso = int((completados / total_enlaces) * 100)
                    barra.progress(min(progreso, 100))
                    if completados % 10 == 0:
                        texto_estado.text(f"Auditando: {completados}/{total_enlaces}...")
            
            barra.progress(100)
            texto_estado.success("✅ Proceso Completado.")
            
            df = pd.DataFrame(resultados_finales)
            
            # --- FASE 3: VISUALIZACIÓN (TABS) ---
            st.write("---")
            tab1, tab2, tab3 = st.tabs(["📄 Datos Detallados", "📡 Hallazgos del Rastreador", "📊 Tablero Gráfico"])
            
            # TAB 1
            with tab1:
                st.subheader("Base de Datos Completa")
                st.dataframe(df)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Todo (CSV)", csv, "auditoria_completa_lab.csv", "text/csv")
                
            # TAB 2
            with tab2:
                st.subheader("Resultados del Rastreador")
                df_sospechosos = df[df['Rastreador'].str.contains("🔍")]
                
                col_s1, col_s2 = st.columns(2)
                col_s1.metric("Total Coincidencias", len(df_sospechosos))
                
                if not df_sospechosos.empty:
                    conteo_palabras = df_sospechosos['Rastreador'].value_counts()
                    col_s2.bar_chart(conteo_palabras) 
                    st.error("Registros que contienen las palabras clave:")
                    st.dataframe(df_sospechosos)
                else:
                    st.success("El Rastreador no encontró ninguna palabra clave EN LOS ENLACES analizados.")

            # TAB 3
            with tab3:
                st.subheader("Análisis de Accesibilidad e Impacto")
                
                c_graf1, c_graf2 = st.columns(2)
                
                # Gráfico Pastel
                with c_graf1:
                    st.markdown("#### Índice Global")
                    conteo_tipos = df['Tipo'].value_counts()
                    fig1, ax1 = plt.subplots()
                    colores = ['#66b3ff', '#ff9999', '#ffcc99', '#ff6666']
                    ax1.pie(conteo_tipos, labels=conteo_tipos.index, autopct='%1.1f%%', startangle=90, colors=colores)
                    ax1.axis('equal') 
                    st.pyplot(fig1)

                # Gráfico Barras (Errores)
                with c_graf2:
                    st.markdown("#### Taxonomía de Errores")
                    df_errores = df[df['Tipo'] != "Accesible"]
                    if not df_errores.empty:
                        conteo_estados = df_errores['Estado'].value_counts()
                        st.bar_chart(conteo_estados)
                    else:
                        st.info("Sin errores técnicos.")

                st.write("---")
                st.markdown("#### Mapa de Calor (Hojas vs Estado)")
                pivot = pd.crosstab(df['Hoja'], df['Tipo'])
                st.dataframe(pivot.style.background_gradient(cmap="Reds"))

st.write("---")
st.markdown("##### 🧪 MODO PRUEBAS - Rama: `pruebas`")
