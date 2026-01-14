import streamlit as st
import pandas as pd
import requests
from openpyxl import load_workbook
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import matplotlib.pyplot as plt
import seaborn as sns # Opcional para mejores colores, pero usaremos nativo si no está

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Verificador - MODO PRUEBAS", page_icon="🧪", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.warning("⚠️ ESTÁS EN MODO PRUEBAS (LABORATORIO)")
    st.header("🔍 Configuración del Sabueso")
    
    # --- CONFIGURACIÓN DE BÚSQUEDA ---
    st.info("Escribe palabras clave para identificar información específica dentro del texto o la URL.")
    texto_busqueda = st.text_area("Palabras a buscar:", value="reservado, confidencial, inexistente, prueba, vacio, no aplica")
    lista_palabras = [p.strip().lower() for p in texto_busqueda.split(',') if p.strip()]
    
    st.write("---")
    st.header("Sobre esta herramienta")
    st.info("🎓 App desarrollada dentro del trabajo de doctorado de Fernando Gamez Reyes.")
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
