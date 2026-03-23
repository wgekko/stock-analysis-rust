import streamlit as st
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime

# Configuración de página
st.set_page_config(layout="wide", page_title="S&R Analysis")
st.header(":material/reorder: Niveles de Soporte y Resistencia con Señales- RSI")

# ==========================================
# FUNCIONES LÓGICAS DINÁMICAS (PORCENTUALES)
# ==========================================

def support(df, l, n1, n2):
    if (df.Low.iloc[l-n1:l].min() < df.Low.iloc[l] or 
        df.Low.iloc[l+1:l+n2+1].min() < df.Low.iloc[l]):
        return 0
    
    body = abs(df.Open.iloc[l] - df.Close.iloc[l])
    lower_wick = min(df.Open.iloc[l], df.Close.iloc[l]) - df.Low.iloc[l]
    
    # Umbral dinámico del 0.05% del precio para la mecha
    threshold = df.Close.iloc[l] * 0.0005 
    if (lower_wick > body) and (lower_wick > threshold): 
        return 1
    return 0

def resistance(df, l, n1, n2):
    if (df.High.iloc[l-n1:l].max() > df.High.iloc[l] or 
        df.High.iloc[l+1:l+n2+1].max() > df.High.iloc[l]):
        return 0
    
    body = abs(df.Open.iloc[l] - df.Close.iloc[l])
    upper_wick = df.High.iloc[l] - max(df.Open.iloc[l], df.Close.iloc[l])
    
    threshold = df.Close.iloc[l] * 0.0005
    if (upper_wick > body) and (upper_wick > threshold):
        return 1
    return 0

def close_level(l, levels, lim, df, mode="res"):
    if not levels: return 0
    price = df.High.iloc[l] if mode == "res" else df.Low.iloc[l]
    
    closest_level = min(levels, key=lambda x: abs(x - price))
    
    distancia_real = abs(price - closest_level)
    umbral_precio = price * lim # 'lim' es el porcentaje (ej. 0.005 para 0.5%)
    
    if distancia_real <= umbral_precio:
        if mode == "res":
            c3 = min(df.Open.iloc[l], df.Close.iloc[l]) < closest_level
            return closest_level if c3 else 0
        else:
            c3 = max(df.Open.iloc[l], df.Close.iloc[l]) > closest_level
            return closest_level if c3 else 0
    return 0

def check_candle_signal(l, n1, n2, backCandles, df, proximity_pct):
    ss, rr = [], []
    for subrow in range(max(0, l - backCandles), l - n2):
        if support(df, subrow, n1, n2): ss.append(df.Low.iloc[subrow])
        if resistance(df, subrow, n1, n2): rr.append(df.High.iloc[subrow])
    
    # Merging de niveles cercanos (0.2% de separación)
    levels = sorted(list(set(ss + rr)))
    clean_levels = []
    if levels:
        clean_levels.append(levels[0])
        for i in range(1, len(levels)):
            if abs(levels[i] - levels[i-1]) > (levels[i] * 0.002):
                clean_levels.append(levels[i])
                
    cR = close_level(l, clean_levels, proximity_pct, df, "res")
    cS = close_level(l, clean_levels, proximity_pct, df, "sup")
    
    if cR and df.RSI.iloc[l-1] < 50: 
        return 1 # VENTA
    elif cS and df.RSI.iloc[l-1] > 50:
        return 2 # COMPRA
    return 0

# ======================
# INTERFAZ CONTAINER
# ======================
with st.container(border=True):
    st.subheader(":material/settings: Parámetros")
    ticker = st.text_input("Ticker", "AMD")
    start_date = st.date_input("Fecha Inicio", datetime.date(2023, 1, 1))
    
    st.divider()
    n1 = st.slider("Velas previas (n1)", 2, 15, 5)
    n2 = st.slider("Velas posteriores (n2)", 2, 15, 5)
    proximity = st.slider("Proximidad al nivel (%)", 0.1, 2.0, 0.5) / 100
    backCandles = st.number_input("Lookback histórico", value=150)
    limit_view = st.slider("Velas a mostrar en gráfico", 50, 500, 150)

# ======================
# EJECUCIÓN
# ======================
if st.button("Ejecutar Análisis"):
    try:
        with st.spinner('Procesando datos y niveles...'):
            df = pdr.DataReader(ticker, "stooq", start_date).sort_index()
            
            if df.empty:
                st.error("No se encontraron datos.")
            else:
                df['RSI'] = ta.rsi(df.Close, length=14)
                df = df.dropna()

                # Recoger datos en formato lista por si se requieren en Rust u otro motor
                close_list = df['Close'].values.tolist()
                high_list = df['High'].values.tolist()
                low_list = df['Low'].values.tolist()

                signals = [0] * len(df)
                analizar_desde = max(backCandles + n1, len(df) - 300)
                
                for row in range(analizar_desde, len(df) - n2):
                    signals[row] = check_candle_signal(row, n1, n2, backCandles, df, proximity)
                
                df["signal"] = signals
                df_plot = df.tail(limit_view).copy()
                
                # Gráfico
                fig = go.Figure(data=[go.Candlestick(
                    x=df_plot.index, open=df_plot.Open, high=df_plot.High, 
                    low=df_plot.Low, close=df_plot.Close, name="Precio"
                )])

                # Dibujar Señales con Texto y Marcador
                df_sig = df_plot[df_plot['signal'] != 0]
                
                if not df_sig.empty:
                    fig.add_trace(go.Scatter(
                        x=df_sig.index,
                        # Mayor margen vertical para dar espacio al texto
                        y=df_sig.apply(lambda x: x.Low * 0.965 if x.signal == 2 else x.High * 1.035, axis=1),
                        mode="markers+text",
                        text=["COMPRA" if s == 2 else "VENTA" for s in df_sig['signal']],
                        textposition=["bottom center" if s == 2 else "top center" for s in df_sig['signal']],
                        textfont=dict(
                            size=12,
                            color=["#39FF14" if s == 2 else "#FF3131" for s in df_sig['signal']]
                        ),
                        marker=dict(
                            symbol=["triangle-up" if s == 2 else "triangle-down" for s in df_sig['signal']],
                            color=["#39FF14" if s == 2 else "#FF3131" for s in df_sig['signal']],
                            size=15,
                            line=dict(width=1, color='white')
                        ),
                        name="Señales S/R"
                    ))

                fig.update_layout(
                    height=750, 
                    template="plotly_dark", 
                    paper_bgcolor='black', 
                    plot_bgcolor='black', 
                    xaxis_rangeslider_visible=False,
                    title=f"Estrategia de Soportes y Resistencias: {ticker}"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if not df_sig.empty:
                    st.success(f"Se detectaron {len(df_sig)} señales en el periodo visible.")
                    st.dataframe(df_sig[['Open', 'High', 'Low', 'Close', 'RSI', 'signal']])
                else:
                    st.info("No se detectaron señales de S/R con estos parámetros.")

    except Exception as e:
        st.error(f"Error técnico: {e}")