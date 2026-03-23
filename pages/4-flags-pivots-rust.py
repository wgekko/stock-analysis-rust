import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime
from scipy.stats import linregress

st.set_page_config(layout="wide", page_title="Pattern Recognition")
st.header(":material/Search: Reconocimiento de Patrones")

# --- FUNCIONES LÓGICAS (CORREGIDAS) ---

def pivotid(df1, l, n1, n2):
    # Usamos .iloc para evitar problemas con índices de fecha
    if l-n1 < 0 or l+n2 >= len(df1):
        return 0
    pividlow, pividhigh = 1, 1
    low_val = df1.Low.iloc[l]
    high_val = df1.High.iloc[l]
    
    for i in range(l-n1, l+n2+1):
        if low_val > df1.Low.iloc[i]: pividlow = 0
        if high_val < df1.High.iloc[i]: pividhigh = 0
        
    if pividlow and pividhigh: return 3
    elif pividlow: return 1
    elif pividhigh: return 2
    else: return 0

# --- INTERFAZ ---

with st.container(border=True):
    st.subheader(":material/settings_alert: Configuración")
    ticker = st.text_input("Ticker", "AAPL")
    start = st.date_input("Inicio", datetime.date(2022, 1, 1))
    end = st.date_input("Fin", datetime.date.today())
    piv_window = st.number_input("Ventana Pivot", value=3, min_value=1)

if st.button("Ejecutar Análisis"):
    try:
        with st.spinner('Descargando y procesando...'):
            df = pdr.DataReader(ticker, "stooq", start, end).sort_index()

            if df.empty:
                st.error("No hay datos.")
            else:
                # 1. Calculamos pivots como una lista de enteros (INT)
                pivots = [pivotid(df, i, piv_window, piv_window) for i in range(len(df))]
                df['pivot'] = pivots

                # 2. Creamos pointpos asegurando que sea FLOAT puro
                # IMPORTANTE: Usamos float('nan') para que no se mezcle con tipos datetime
                def get_pointpos(row):
                    if row['pivot'] == 1: return float(row['Low'] * 0.99)
                    if row['pivot'] == 2: return float(row['High'] * 1.01)
                    return float('nan') 

                df['pointpos'] = df.apply(get_pointpos, axis=1)

                # --- GRÁFICO RESALTADO ---
                st.subheader(f":material/pivot_table_chart: Pivots Detectados en {ticker}")
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df.index, open=df['Open'], high=df['High'], 
                    low=df['Low'], close=df['Close'],
                    increasing_line_color='#00FF00', decreasing_line_color='#FF3131',
                    name="Precio"
                ))

                # Puntos de Pivot (Cian)
                fig.add_trace(go.Scatter(
                    x=df.index, y=df['pointpos'], 
                    mode="markers", 
                    marker=dict(size=8, color="#00FFFF", symbol="diamond"),
                    name="Pivots"
                ))

                fig.update_layout(height=700, template="plotly_dark", 
                                paper_bgcolor='black', plot_bgcolor='black',
                                xaxis_rangeslider_visible=False)
                
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error detectado: {e}")