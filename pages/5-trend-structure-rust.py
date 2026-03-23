import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime

# Intentar importar el motor acelerado
try:
    import oscilador
except ImportError:
    st.error("Motor 'oscilador' no detectado. Ejecuta 'maturin develop'.")

st.set_page_config(layout="wide", page_title="Trend & Structure", page_icon=":material/monitoring:")
st.header(":material/monitoring: Trend & Structure")

# ======================
# LÓGICA DE APOYO (PYTHON)
# ======================
def detect_structure(df, candle, backcandles, window):
    if candle - backcandles - window < 0: return 0
    localdf = df.iloc[candle - backcandles - window : candle - window]
    
    # Usamos las columnas ya procesadas por Rust
    highs = localdf[localdf['isPivot'] == 1].High.tail(3).values
    idxhighs = localdf[localdf['isPivot'] == 1].High.tail(3).index
    lows = localdf[localdf['isPivot'] == 2].Low.tail(3).values
    idxlows = localdf[localdf['isPivot'] == 2].Low.tail(3).index

    if len(highs) == 3 and len(lows) == 3:
        order_condition = (idxlows[0] < idxhighs[0] < idxlows[1] < idxhighs[1] < idxlows[2] < idxhighs[2])
        pattern_1 = (lows[0] < highs[0] and lows[1] > lows[0] and lows[1] < highs[0] and
                    highs[1] > highs[0] and lows[2] > lows[1] and lows[2] < highs[1])
        if order_condition and pattern_1: return 1
    return 0

# ======================
# UI CONFIG
# ======================
with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    ticker = col1.text_input("Ticker", "AMD")
    start = col2.date_input("Inicio", datetime.date(2023, 1, 1))
    ema_len = col3.number_input("Longitud EMA", value=150)
    
    piv_win = st.slider("Ventana Pivot", 1, 10, 5)
    back_trend = st.slider("Velas para Tendencia", 5, 50, 15)

# ======================
# EJECUCIÓN
# ======================
if st.button("Ejecutar Análisis"):
    try:
        with st.spinner('Consultando Stooq y procesando en Rust...'):
            df = pdr.DataReader(ticker, "stooq", start).sort_index()
            
            # Preparar datos para Rust
            closes = df.Close.tolist()
            highs = df.High.tolist()
            lows = df.Low.tolist()
            opens = df.Open.tolist()

            # 1. Cálculos de Indicadores (RUST)
            df['EMA'] = oscilador.ema_py(closes, int(ema_len))
            df['RSI'] = oscilador.rsi(closes, 12)

            # 2. Tendencia (RUST - Reemplaza tu bucle for anidado)
            df['EMASignal'] = oscilador.ema_trend_filter(opens, closes, df['EMA'].tolist(), back_trend)

            # 3. Pivots (RUST - Reemplaza tu función is_pivot)
            df['isPivot'] = oscilador.detect_pivots(highs, lows, piv_win)
            
            # Posicionamiento de etiquetas de Pivots
            df['pointpos'] = np.nan
            df.loc[df['isPivot'] == 2, 'pointpos'] = df['Low'] * 0.99
            df.loc[df['isPivot'] == 1, 'pointpos'] = df['High'] * 1.01

            # 4. Estructura Compleja
            df['pattern'] = [detect_structure(df, i, 35, piv_win) for i in range(len(df))]
            patterns_found = df[df['pattern'] == 1]

        # ======================
        # GRÁFICO
        # ======================
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="Precio"))
        fig.add_trace(go.Scatter(x=df.index, y=df.EMA, line=dict(color='orange', width=1.5), name="EMA Trend"))
        
        # Marcadores de Pivots (Calculados en Rust)
        fig.add_trace(go.Scatter(x=df.index, y=df.pointpos, mode="markers", 
                                marker=dict(size=8, color="#BC13FE", symbol="diamond"), name="Pivot"))

        # Señales de tendencia
        df_up = df[df['EMASignal'] == 2]
        fig.add_trace(go.Scatter(x=df_up.index, y=df_up.Low * 0.98, mode="markers", 
                                marker=dict(symbol="triangle-up", color="#00FF00", size=8), name="Bull Trend"))

        fig.update_layout(height=750, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        if not patterns_found.empty:
            st.success(f"Estructuras detectadas: {len(patterns_found)}")
            st.dataframe(patterns_found[['Close', 'EMA', 'RSI', 'EMASignal']])

    except Exception as e:
        st.error(f"Error: {e}")