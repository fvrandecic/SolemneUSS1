import streamlit as st
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================
# Configuración inicial de la página
# ==========================================
st.set_page_config(
    page_title="Análisis de Datos - Gobierno de Chile",
    page_icon="🇨🇱",
    layout="wide"
)

# ==========================================
# Funciones de interacción con la API
# ==========================================

@st.cache_data
def buscar_datasets(termino_busqueda):
    """
    Busca paquetes de datos en datos.gob.cl usando la API REST (GET).
    Utilizamos json explícitamente para cumplir el requisito de la librería.
    """
    url = f"https://datos.gob.cl/api/3/action/package_search"
    params = {"q": termino_busqueda, "rows": 10} # Buscamos hasta 10 datasets relacionados
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Verifica si la petición fue exitosa (código 200)
        
        # Uso explícito de la librería json para el manejo de datos en formato JSON
        data = json.loads(response.text) 
        
        recursos_activos = {}
        if data.get('success'):
            for paquete in data['result']['results']:
                for recurso in paquete['resources']:
                    # Filtramos solo los recursos que permiten consultas a través de la API Datastore
                    if recurso.get('datastore_active'):
                        nombre = f"{paquete['title']} - {recurso['name']}"
                        recursos_activos[nombre] = recurso['id']
        return recursos_activos
    except Exception as e:
        st.error(f"Error al conectar con la API de búsqueda: {e}")
        return {}

@st.cache_data
def obtener_datos_recurso(resource_id, limite=150):
    """
    Obtiene los registros de un recurso específico mediante datastore_search.
    """
    url = "https://datos.gob.cl/api/3/action/datastore_search"
    params = {"resource_id": resource_id, "limit": limite}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = json.loads(response.text)
        
        if data.get('success'):
            return data['result']['records']
        return []
    except Exception as e:
        st.error(f"Error al obtener los datos del recurso: {e}")
        return []

# ==========================================
# Interfaz de Usuario (Streamlit)
# ==========================================

st.title("📊 Análisis y Presentación de Datos - API datos.gob.cl")
st.markdown("""
Esta aplicación permite extraer datos en tiempo real desde la plataforma de datos abiertos del Gobierno de Chile mediante consultas API REST (`GET`), analizar los resultados mediante `pandas` y visualizarlos con `matplotlib`.
""")

# --- BARRA LATERAL ---
st.sidebar.header("1. Búsqueda de Datos")
st.sidebar.write("Ingresa una palabra clave para buscar datasets disponibles (ej: *salud*, *educacion*, *economia*):")

termino = st.sidebar.text_input("Palabra clave:", value="salud")
recursos_dict = buscar_datasets(termino)

if not recursos_dict:
    st.warning(f"No se encontraron datasets activos consultables vía API para el término '{termino}'. Intenta con otra palabra.")
else:
    # Selección del Dataset
    dataset_seleccionado = st.sidebar.selectbox("Selecciona un Dataset:", list(recursos_dict.keys()))
    resource_id = recursos_dict[dataset_seleccionado]
    
    limite_filas = st.sidebar.slider("Cantidad de registros a extraer:", 10, 1000, 200)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Objetivos del Proyecto:**")
    st.sidebar.info(
        "✔️ Integración API REST (GET)\n"
        "✔️ Parseo de JSON\n"
        "✔️ Análisis con Pandas\n"
        "✔️ Visualización Matplotlib y Streamlit"
    )

    # --- CUERPO PRINCIPAL ---
    st.header(f"Dataset: {dataset_seleccionado}")
    
    with st.spinner("Descargando datos desde la API..."):
        registros = obtener_datos_recurso(resource_id, limite=limite_filas)
    
    if registros:
        # Requisito: Análisis de datos con pandas
        df = pd.DataFrame(registros)
        
        # Limpieza de datos básica (intentar convertir columnas a numéricas para análisis)
        for col in df.columns:
            # Ignoramos la columna '_id' propia de CKAN
            if col != '_id':
                df[col] = pd.to_numeric(df[col], errors='ignore')

        # 1. Exploración Cruda
        st.subheader("📌 Exploración de Datos Crudos")
        st.write(f"Se extrajeron **{len(df)}** registros y **{len(df.columns)}** columnas.")
        st.dataframe(df.head(10)) # Mostramos una muestra
        
        # 2. Interacción de Streamlit: Filtrado
        st.subheader("🔍 Filtrado Interactivo")
        
        col1, col2 = st.columns(2)
        with col1:
            col_a_filtrar = st.selectbox("Selecciona una columna para filtrar:", df.columns)
        
        # Obtenemos valores únicos de esa columna (convirtiendo a string para evitar errores de tipo)
        valores_unicos = df[col_a_filtrar].astype(str).unique()
        
        with col2:
            valor_filtro = st.selectbox("Selecciona el valor específico:", valores_unicos)
            
        # Aplicar el filtro usando Pandas
        df_filtrado = df[df[col_a_filtrar].astype(str) == valor_filtro]
        st.write(f"Resultados encontrados: **{len(df_filtrado)}**")
        st.dataframe(df_filtrado)

        # 3. Presentación de resultados (Matplotlib)
        st.subheader("📈 Visualización Gráfica")
        st.write("Genera un gráfico dinámico analizando las variables del Dataset.")
        
        # Separar columnas categóricas y numéricas para ofrecer mejores opciones de gráficos
        cols_numericas = df.select_dtypes(include=['number']).columns.tolist()
        # Filtramos '_id' de las numéricas ya que no tiene valor analítico
        if '_id' in cols_numericas: cols_numericas.remove('_id') 
        cols_categoricas = df.select_dtypes(include=['object', 'string']).columns.tolist()
        
        if len(cols_categoricas) > 0:
            tipo_grafico = st.radio("Selecciona el tipo de análisis:", ["Frecuencia de Categorías", "Relación Numérica por Categoría"])
            
            fig, ax = plt.subplots(figsize=(10, 5))
            
            if tipo_grafico == "Frecuencia de Categorías":
                col_cat = st.selectbox("Elige la variable a contar (Eje X):", cols_categoricas)
                
                # Análisis de datos con Pandas (Conteo)
                conteo = df[col_cat].value_counts().head(10) # Top 10 para no saturar
                
                # Gráfico con Matplotlib
                conteo.plot(kind='bar', color='dodgerblue', edgecolor='black', ax=ax)
                ax.set_title(f"Top 10 frecuencias de '{col_cat}'", fontweight='bold')
                ax.set_ylabel("Cantidad de Registros")
                ax.set_xlabel(col_cat)
                
            elif tipo_grafico == "Relación Numérica por Categoría":
                if len(cols_numericas) > 0:
                    c1, c2 = st.columns(2)
                    with c1:
                        eje_x = st.selectbox("Eje X (Agrupación Categórica):", cols_categoricas)
                    with c2:
                        eje_y = st.selectbox("Eje Y (Suma Numérica):", cols_numericas)
                    
                    # Análisis con Pandas: Agrupar y sumar
                    datos_agrupados = df.groupby(eje_x)[eje_y].sum().sort_values(ascending=False).head(15)
                    
                    # Gráfico con Matplotlib
                    datos_agrupados.plot(kind='bar', color='coral', edgecolor='black', ax=ax)
                    ax.set_title(f"Suma total de '{eje_y}' agrupado por '{eje_x}' (Top 15)", fontweight='bold')
                    ax.set_ylabel(f"Suma de {eje_y}")
                    ax.set_xlabel(eje_x)
                else:
                    st.warning("Este dataset no contiene variables numéricas válidas para sumar.")
                    
            # Mejorar apariencia del gráfico
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Renderizar en Streamlit
            st.pyplot(fig)
            
        else:
            st.info("No se detectaron columnas categóricas suficientes para generar un gráfico automático en este dataset.")
            
    else:
        st.error("No se encontraron registros en el dataset seleccionado o la API devolvió una lista vacía.")