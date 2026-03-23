import streamlit as st
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(layout="wide", page_title="S&R Analysis")
st.header(":material/reorder: Análisis de Soportes, Resistencias y Señales RSI")

# ==========================================
# 2. FUNCIONES LÓGICAS (ADAPTADAS A ACCIONES)
# ==========================================

def support(df, l, n1, n2):
    """Detecta si la vela en la posición 'l' es un mínimo local con rechazo."""
    if (df['Low'].iloc[l-n1:l].min() < df['Low'].iloc[l] or 
        df['Low'].iloc[l+1:l+n2+1].min() < df['Low'].iloc[l]):
        return 0
    
    body = abs(df['Open'].iloc[l] - df['Close'].iloc[l])
    lower_wick = min(df['Open'].iloc[l], df['Close'].iloc[l]) - df['Low'].iloc[l]
    
    # Umbral dinámico: la mecha debe ser al menos el 0.05% del precio
    threshold = df['Close'].iloc[l] * 0.0005 
    if (lower_wick > body) and (lower_wick > threshold): 
        return 1
    return 0

def resistance(df, l, n1, n2):
    """Detecta si la vela en la posición 'l' es un máximo local con rechazo."""
    if (df['High'].iloc[l-n1:l].max() > df['High'].iloc[l] or 
        df['High'].iloc[l+1:l+n2+1].max() > df['High'].iloc[l]):
        return 0
    
    body = abs(df['Open'].iloc[l] - df['Close'].iloc[l])
    upper_wick = df['High'].iloc[l] - max(df['Open'].iloc[l], df['Close'].iloc[l])
    
    threshold = df['Close'].iloc[l] * 0.0005
    if (upper_wick > body) and (upper_wick > threshold):
        return 1
    return 0

def close_level(l, levels, lim_pct, df, mode="res"):
    """Verifica si el precio actual está cerca de un nivel histórico."""
    if not levels: return 0
    price = df['High'].iloc[l] if mode == "res" else df['Low'].iloc[l]
    
    closest_level = min(levels, key=lambda x: abs(x - price))
    distancia_relativa = abs(price - closest_level) / price
    
    if distancia_relativa <= lim_pct:
        if mode == "res":
            # Resistencia: El cuerpo debe cerrar por debajo del nivel
            return closest_level if min(df['Open'].iloc[l], df['Close'].iloc[l]) < closest_level else 0
        else:
            # Soporte: El cuerpo debe cerrar por encima del nivel
            return closest_level if max(df['Open'].iloc[l], df['Close'].iloc[l]) > closest_level else 0
    return 0

def check_candle_signal(l, n1, n2, backCandles, df, proximity_pct):
    """Escanea el historial, limpia niveles y genera la señal final."""
    ss, rr = [], []
    # Buscar niveles en la ventana histórica (backCandles)
    for subrow in range(max(0, l - backCandles), l - n2):
        if support(df, subrow, n1, n2): ss.append(df['Low'].iloc[subrow])
        if resistance(df, subrow, n1, n2): rr.append(df['High'].iloc[subrow])
    
    # Unificar niveles muy cercanos (Merging al 0.2%)
    all_levels = sorted(list(set(ss + rr)))
    clean_levels = []
    if all_levels:
        clean_levels.append(all_levels[0])
        for i in range(1, len(all_levels)):
            if abs(all_levels[i] - all_levels[i-1]) > (all_levels[i] * 0.002):
                clean_levels.append(all_levels[i])
                
    cR = close_level(l, clean_levels, proximity_pct, df, "res")
    cS = close_level(l, clean_levels, proximity_pct, df, "sup")
    
    # Filtro RSI: Evitar señales en zonas de agotamiento extremo
    if cR and df['RSI'].iloc[l-1] < 55: 
        return 1 # VENTA
    elif cS and df['RSI'].iloc[l-1] > 45:
        return 2 # COMPRA
    return 0

# ======================
# 3. INTERFAZ CONTAINER
# ======================
with st.container(border=True):
    st.subheader("⚙️ Configuración")
    ticker = st.text_input("Ticker", "AMD")
    start_date = st.date_input("Analizar desde", datetime.date(2023, 1, 1))
    
    st.divider()
    st.subheader("Sensibilidad S/R")
    n1 = st.slider("Velas previas (Fractal)", 2, 15, 5)
    n2 = st.slider("Velas posteriores (Fractal)", 2, 15, 5)
    proximity = st.slider("Proximidad al nivel (%)", 0.1, 2.0, 0.6) / 100
    backCandles = st.number_input("Memoria histórica (Velas)", value=150)
    limit_view = st.slider("Velas a mostrar", 50, 500, 150)

# ======================
# 4. EJECUCIÓN PRINCIPAL
# ======================
if st.button("Ejecutar Análisis Técnico"):
    try:
        with st.spinner(f'Descargando y procesando {ticker}...'):
            # Obtención de datos
            df = pdr.DataReader(ticker, "stooq", start_date).sort_index()
            
            if df.empty:
                st.error("No se encontraron datos para este ticker.")
            else:
                # Indicadores y limpieza
                df['RSI'] = ta.rsi(df['Close'], length=14)
                df = df.dropna().copy() # .copy() evita el error de SettingWithCopy

                # Cálculo de señales
                signals = [0] * len(df)
                start_idx = max(backCandles + n1, len(df) - limit_view)
                
                for row in range(start_idx, len(df) - n2):
                    signals[row] = check_candle_signal(row, n1, n2, backCandles, df, proximity)
                
                df["signal"] = signals

                # --- 5. VISUALIZACIÓN ---
                df_plot = df.tail(limit_view).copy()
                
                fig = go.Figure(data=[go.Candlestick(
                    x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
                    low=df_plot['Low'], close=df_plot['Close'], name="Market"
                )])

                # Filtrar señales para graficar
                df_sig = df_plot[df_plot['signal'] != 0]
                
                if not df_sig.empty:
                    fig.add_trace(go.Scatter(
                        x=df_sig.index,
                        # Posicionamiento: 3% de margen para que el texto sea legible
                        y=df_sig.apply(lambda x: x['Low'] * 0.97 if x['signal'] == 2 else x['High'] * 1.03, axis=1),
                        mode="markers+text",
                        text=["COMPRA" if s == 2 else "VENTA" for s in df_sig['signal']],
                        textposition=["bottom center" if s == 2 else "top center" for s in df_sig['signal']],
                        textfont=dict(size=12, color="white"),
                        marker=dict(
                            symbol=["triangle-up" if s == 2 else "triangle-down" for s in df_sig['signal']],
                            color=["#00FF00" if s == 2 else "#FF0000" for s in df_sig['signal']],
                            size=18,
                            line=dict(width=1, color='white')
                        ),
                        name="Señales de Entrada"
                    ))

                # Estética del Gráfico
                fig.update_layout(
                    height=800, 
                    template="plotly_dark", 
                    paper_bgcolor='black', 
                    plot_bgcolor='#0a0a0a', 
                    xaxis_rangeslider_visible=False,
                    title=f"Niveles Críticos y Señales: {ticker}",
                    yaxis_title="Precio (USD)"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Resumen de señales en tabla
                if not df_sig.empty:
                    st.success(f"Se han identificado {len(df_sig)} oportunidades potenciales.")
                    # Formatear la tabla para el usuario
                    df_resumen = df_sig[['Open', 'High', 'Low', 'Close', 'RSI', 'signal']].copy()
                    df_resumen['Acción'] = df_resumen['signal'].map({1: 'VENTA', 2: 'COMPRA'})
                    st.dataframe(df_resumen.drop(columns=['signal']), use_container_width=True)
                else:
                    st.info("No se detectaron señales claras con la sensibilidad actual. Prueba aumentando la 'Proximidad' en el panel lateral.")

    except Exception as e:
        st.error(f"Error crítico en el proceso: {e}")