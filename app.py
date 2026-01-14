import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import matplotlib.pyplot as plt

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Verificador de Transparencia", page_icon="📊", layout="wide")

# --- 2. BARRA LATERAL (SIEMPRE VISIBLE) ---
with st.sidebar:
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
    st.write("---")
    st.success("✅ Esta aplicación es de uso académico y gratuito para la verificación de obligaciones de transparencia.")
    
    st.write("---")
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.usuario_valido = False
        st.rerun()

# ==========================================
# 🔐 3. EL BÚNKER (SEGURIDAD)
# ==========================================

if "usuario_valido" not in st.session_state:
    st.session_state.usuario_valido = False

if not st.session_state.usuario_valido:
    st.markdown("# 🔒 Acceso Privado - Doctorado")
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

st.title("Verificador de Hipervínculos & Tablero de Impacto")
st.markdown("Herramienta de auditoría digital para obligaciones de transparencia.")

archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado correctamente.")
    
    if st.button("🚀 Iniciar Auditoría y Análisis"):
        # --- PROCESAMIENTO ---
        st.write("⚙️ Procesando archivo y verificando enlaces en tiempo real...")
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
                            "Estado": "Pendiente",
                            "Tipo": "Pendiente",
                            "Código": 0
                        })
        
        total_enlaces = len(lista_cruda)
        
        if total_enlaces == 0:
            st.warning("No se encontraron enlaces en el archivo.")
        else:
            # Barra de progreso
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
                        texto_estado.text(f"Auditando: {completados}/{total_enlaces} enlaces...")
            
            barra.progress(100)
            texto_estado.success("✅ Auditoría Finalizada.")
            
            # Crear DataFrame
            df = pd.DataFrame(resultados_finales)
            
            # --- ZONA DE RESULTADOS (TABS) ---
            tab1, tab2 = st.tabs(["📄 Resultados Detallados", "📊 Tablero de Impacto (Gráficos)"])
            
            # --- PESTAÑA 1: DATOS ---
            with tab1:
                st.subheader("Listado de Verificación")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Enlaces", len(df))
                c2.metric("Accesibles", len(df[df['Tipo'] == "Accesible"]))
                errores = len(df[df['Tipo'] != "Accesible"])
                c3.metric("Con Incidencias", errores, delta_color="inverse")
                
                st.dataframe(df)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Reporte CSV", csv, "reporte_auditoria.csv", "text/csv")
            
            # --- PESTAÑA 2: GRÁFICOS ---
            with tab2:
                st.subheader("Análisis Visual de Resultados")
                col_graf1, col_graf2 = st.columns(2)
                
                # GRÁFICO 1: Pastel
                with col_graf1:
                    st.markdown("#### 1. Índice Global de Accesibilidad")
                    conteo_tipos = df['Tipo'].value_counts()
                    fig1, ax1 = plt.subplots()
                    colores = ['#66b3ff', '#ff9999', '#ffcc99', '#ff6666']
                    ax1.pie(conteo_tipos, labels=conteo_tipos.index, autopct='%1.1f%%', startangle=90, colors=colores)
                    ax1.axis('equal') 
                    st.pyplot(fig1)

                # GRÁFICO 2: Barras
                with col_graf2:
                    st.markdown("#### 2. Detalle de Incidencias")
                    df_errores = df[df['Tipo'] != "Accesible"]
                    if not df_errores.empty:
                        conteo_estados = df_errores['Estado'].value_counts()
                        st.bar_chart(conteo_estados)
                    else:
                        st.success("¡Felicidades! No hay errores para graficar.")

                st.write("---")
                
                # GRÁFICO 3: Mapa de Calor
                st.markdown("#### 3. Mapa de Opacidad por Área (Hoja de Excel)")
                pivot = pd.crosstab(df['Hoja'], df['Tipo'])
                st.dataframe(pivot.style.background_gradient(cmap="Reds", subset=pivot.columns.difference(['Accesible'])))

st.write("---")
st.markdown("##### 🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
