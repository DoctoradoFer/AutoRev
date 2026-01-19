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

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado del Mtro. Fernando Gamez Reyes.")
    st.write("---")
    st.success("✅ Herramienta de auditoría para la verificación de obligaciones de transparencia.")
    
    st.write("---")
    if st.button("🔒 Cerrar Sesión"):
        st.session_state.usuario_valido = False
        st.rerun()

# --- 3. SEGURIDAD ---
if "usuario_valido" not in st.session_state:
    st.session_state.usuario_valido = False

if not st.session_state.usuario_valido:
    st.markdown("# 🔒 Acceso Privado")
    st.info("Ingresa la clave autorizada.")
    clave_ingresada = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if clave_ingresada == "Fernando2026":
            st.session_state.usuario_valido = True
            st.rerun()
        else:
            st.error("⛔ Clave incorrecta.")
    st.stop()

# --- 4. LÓGICA DE VERIFICACIÓN ---
def crear_sesion_segura():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retry))
    session.mount('https://', HTTPAdapter(max_retries=retry))
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
            
    except Exception:
        datos_enlace['Estado'] = "💀 ERROR CONEXIÓN"
        datos_enlace['Tipo'] = "Fallo Red"
        datos_enlace['Código'] = 0
    finally:
        session.close()
    return datos_enlace

# --- 5. INTERFAZ ---
st.title("Verificador de Hipervínculos & Tablero de Impacto")
st.markdown("Herramienta de auditoría digital para obligaciones de transparencia.")

archivo_subido = st.file_uploader("Carga tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    st.success("Archivo cargado.")
    if st.button("🚀 Iniciar Auditoría"):
        st.write("⚙️ Procesando con 8 motores de verificación...")
        wb = load_workbook(archivo_subido, data_only=False)
        lista_cruda = []
        
        for nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            for row in ws.iter_rows():
                for cell in row:
                    url_encontrada = None
                    if cell.hyperlink:
                        url_encontrada = cell.hyperlink.target
                    elif isinstance(cell.value, str) and str(cell.value).startswith(('http', 'https')):
                        url_encontrada = cell.value
                    
                    if url_encontrada:
                        lista_cruda.append({
                            "Hoja": nombre_hoja,
                            "Coordenada": cell.coordinate,
                            "URL Original": url_encontrada,
                            "Estado": "Pendiente",
                            "Tipo": "Pendiente"
                        })
        
        total = len(lista_cruda)
        if total == 0:
            st.warning("No se encontraron enlaces.")
        else:
            barra = st.progress(0)
            resultados = []
            # AQUÍ ESTÁN TUS 8 ROBOTS 👇
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(verificar_un_enlace, item): item for item in lista_cruda}
                completados = 0
                for future in concurrent.futures.as_completed(futures):
                    resultados.append(future.result())
                    completados += 1
                    barra.progress(int((completados/total)*100))
            
            barra.progress(100)
            st.success("✅ Auditoría Finalizada.")
            df = pd.DataFrame(resultados)
            
            tab1, tab2 = st.tabs(["📄 Datos", "📊 Gráficos"])
            
            with tab1:
                st.dataframe(df)
                st.download_button("📥 Descargar CSV", df.to_csv(index=False).encode('utf-8'), "reporte.csv")
            
            with tab2:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### Índice Global")
                    conteo = df['Tipo'].value_counts()
                    fig1, ax1 = plt.subplots()
                    ax1.pie(conteo, labels=conteo.index, autopct='%1.1f%%', startangle=90, colors=['#66b3ff', '#ff9999', '#ffcc99'])
                    ax1.axis('equal')
                    st.pyplot(fig1)
                with c2:
                    st.markdown("#### Detalle de Errores")
                    df_err = df[df['Tipo'] != "Accesible"]
                    if not df_err.empty:
                        st.bar_chart(df_err['Estado'].value_counts())
                
                st.write("---")
                st.markdown("#### Mapa de Calor (Hojas)")
                pivot = pd.crosstab(df['Hoja'], df['Tipo'])
                st.dataframe(pivot.style.background_gradient(cmap="Reds"))
