import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime
from plotly.subplots import make_subplots

import oscilador

st.set_page_config(layout="wide", page_title="Rust Stock Engine", page_icon=":material/finance_mode:")
st.header(":material/finance_mode: App Trading")

# ======================
# INPUTS CONTAINER
# ======================
with st.container(border=True):
    st.subheader(":material/settings_a""lert: Configuración")
    ticker = st.text_input("Ticker", "AAPL")
    start = st.date_input("Inicio", datetime.date(2022, 1, 1))
    end = st.date_input("Fin", datetime.date.today())
    
    st.divider()
    st.subheader(":material/settings_account_box: Parámetros Breakout")
    n_breakout = st.number_input("Ventana N", value=25, min_value=2)
    t1 = st.slider("Threshold Buy (t1)", 0.0, 1.0, 0.5)
    t2 = st.slider("Threshold Sell (t2)", -1.0, 0.0, -0.5)

# ======================
# LÓGICA DE EJECUCIÓN
# ======================
if st.button("Ejecutar Análisis"):

    try:
        # 1. OBTENCIÓN DE DATOS
        with st.spinner('Descargando datos...'):
            df = pdr.DataReader(ticker, "stooq", start, end).sort_index()

        if df.empty:
            st.error("No se encontraron datos.")
        else:
            # Preparar listas para Rust
            close = df['Close'].values.tolist()
            high = df['High'].values.tolist()
            low = df['Low'].values.tolist()

            # 2. CÁLCULOS MOTOR DE RUST (PARALELO)
            with st.spinner('Procesando en Rust...'):
                sma20 = oscilador.sma(close, 20)
                sma50 = oscilador.sma(close, 50)
                rsi = oscilador.rsi(close, 14)
                bb_mid, bb_up, bb_low = oscilador.bollinger_bands(close, 20, 2)
                macd, macd_signal, macd_hist = oscilador.macd(close)
                atr = oscilador.atr(high, low, close, 14)
                
                # Breakout
                r_max, r_min, r_avg, scaled = oscilador.breakout_oscillator(high, low, close, n_breakout)
                b_signals = oscilador.breakout_signals(scaled, t1, t2)
                
                # Beta y Estrategia
                spy = pdr.DataReader("SPY", "stooq", start, end).sort_index()
                beta = oscilador.beta(close, spy['Close'].values.tolist())
                signals = oscilador.signals(sma20, sma50, rsi)
                strategy = oscilador.backtest(close, signals)

            # 3. ASIGNACIÓN AL DATAFRAME
            df['SMA20'], df['SMA50'], df['RSI'] = sma20, sma50, rsi
            df['BB_UP'], df['BB_LOW'] = bb_up, bb_low
            df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = macd, macd_signal, macd_hist
            df['ATR'] = atr
            df['R_Max'], df['R_Min'], df['ScaledPrice'] = r_max, r_min, scaled
            df['Strategy'] = [0.0] + strategy 
            
            # Puntos visuales para señales Breakout
            def get_pointpos(row):
                if row['B_Signals'] == 2: return row['Low'] * 0.99
                if row['B_Signals'] == 1: return row['High'] * 1.01
                return None
            df['B_Signals'] = b_signals
            df['pointpos'] = df.apply(get_pointpos, axis=1)

            # 4. MÉTRICAS SUPERIORES
            df['Return'] = df['Close'].pct_change().fillna(0)
            df['Equity'] = (1 + df['Strategy']).cumprod()
            df['BuyHold'] = (1 + df['Return']).cumprod()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Beta vs SPY", round(beta, 4))
            c2.metric("Retorno Estrategia", f"{df['Equity'].iloc[-1]:.2f}x")
            c3.metric("Retorno Buy & Hold", f"{df['BuyHold'].iloc[-1]:.2f}x")

            # ======================
            # GRÁFICOS (TODOS VISIBLES)
            # ======================

            # A. PRECIO + BOLLINGER + BREAKOUT CHANNELS
            st.subheader("1. Precio y Canales de Ruptura")
            fig_p = go.Figure()
            fig_p.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Precio"))
            fig_p.add_trace(go.Scatter(x=df.index, y=df['R_Max'], name='BO Max', line=dict(color='#27F5F5', width=1)))
            fig_p.add_trace(go.Scatter(x=df.index, y=df['R_Min'], name='BO Min', line=dict(color='#F5EE27', width=1)))
            fig_p.add_trace(go.Scatter(x=df.index, y=df['pointpos'], mode="markers", marker=dict(size=10, color="#F527C5", symbol="diamond"), name="Señal BO"))
            fig_p.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig_p, use_container_width=True)

            # B. SCALED PRICE (EL OSCILADOR DEL BREAKOUT)
            st.subheader("2. Oscilador Scaled Price")
            fig_sp = go.Figure()
            fig_sp.add_trace(go.Scatter(x=df.index, y=df['ScaledPrice'], line=dict(color='purple'), name="Scaled"))
            fig_sp.add_hline(y=t1, line_dash="dash", line_color="green")
            fig_sp.add_hline(y=t2, line_dash="dash", line_color="red")
            fig_sp.update_layout(height=300, template="plotly_dark")
            st.plotly_chart(fig_sp, use_container_width=True)

            # C. MACD
            st.subheader("3. MACD (Moving Average Convergence Divergence)")
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='cyan')))
            fig_m.add_trace(go.Scatter(x=df.index, y=df['MACD_SIGNAL'], name='Signal', line=dict(color='orange')))
            fig_m.add_trace(go.Bar(x=df.index, y=df['MACD_HIST'], name='Hist'))
            fig_m.update_layout(height=300, template="plotly_dark")
            st.plotly_chart(fig_m, use_container_width=True)

            # D. RSI
            st.subheader("4. RSI (Relative Strength Index)")
            fig_r = go.Figure()
            fig_r.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='magenta')))
            fig_r.add_hline(y=70, line_dash="dash", line_color="red")
            fig_r.add_hline(y=30, line_dash="dash", line_color="green")
            fig_r.update_layout(height=300, template="plotly_dark", yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig_r, use_container_width=True)

            # E. ATR & EQUITY
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("5. Volatilidad (ATR)")
                fig_a = go.Figure()
                fig_a.add_trace(go.Scatter(x=df.index, y=df['ATR'], name='ATR', line=dict(color='yellow')))
                st.plotly_chart(fig_a, use_container_width=True)
                
            with col_right:
                st.subheader("6. Evolución de Capital")
                fig_e = go.Figure()
                fig_e.add_trace(go.Scatter(x=df.index, y=df['Equity'], name='Estrategia', fill='tozeroy'))
                fig_e.add_trace(go.Scatter(x=df.index, y=df['BuyHold'], name='Buy & Hold'))
                st.plotly_chart(fig_e, use_container_width=True)

    except Exception as e:
        st.error(f"Error en el proceso: {e}")