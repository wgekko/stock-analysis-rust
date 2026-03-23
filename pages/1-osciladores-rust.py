
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime
from plotly.subplots import make_subplots

import oscilador

st.set_page_config(layout="wide", page_title="Osciladores", page_icon=":material/finance_mode:")
st.header(":material/bar_chart_4_bars: Osciladores SMA20- SMA50- BBOLINGER-DRAWDOWN-MACD-RSI")

# ======================
# INPUTS
# ======================
ticker = st.text_input("Ticker", "AAPL")
start = st.date_input("Inicio", datetime.date(2022, 1, 1))
end = st.date_input("Fin", datetime.date.today())

with st.container(border=True):
    st.subheader("Parámetros Breakout")
    n_breakout = st.number_input("Ventana N", value=25)
    t1 = st.slider("Threshold Buy (t1)", 0.0, 1.0, 0.5)
    t2 = st.slider("Threshold Sell (t2)", -1.0, 0.0, -0.5)



if st.button("Ejecutar"):

    # ======================
    # DATA
    # ======================
    df = pdr.DataReader(ticker, "stooq", start, end).sort_index()

    close = df['Close'].values.tolist()
    high = df['High'].values.tolist()
    low = df['Low'].values.tolist()

    # ======================
    # INDICADORES (RUST)
    # ======================
    sma20 = oscilador.sma(close, 20)
    sma50 = oscilador.sma(close, 50)
    rsi = oscilador.rsi(close, 14)

    bb_mid, bb_up, bb_low = oscilador.bollinger_bands(close, 20, 2)

    macd, macd_signal, macd_hist = oscilador.macd(close)

    atr = oscilador.atr(high, low, close, 14)


    # ======================
    # BETA vs SPY
    # ======================
    spy = pdr.DataReader("SPY", "stooq", start, end).sort_index()
    beta = oscilador.beta(close, spy['Close'].values.tolist())

    # ======================
    # SEÑALES + BACKTEST
    # ======================
    signals = oscilador.signals(sma20, sma50, rsi)
    strategy = oscilador.backtest(close, signals)

    # ======================
    # DATAFRAME
    # ======================
    df['SMA20'] = sma20
    df['SMA50'] = sma50
    df['RSI'] = rsi

    df['BB_MID'] = bb_mid
    df['BB_UP'] = bb_up
    df['BB_LOW'] = bb_low

    df['MACD'] = macd
    df['MACD_SIGNAL'] = macd_signal
    df['MACD_HIST'] = macd_hist

    df['ATR'] = atr
    df['Strategy'] = [0.0] + strategy

    df['Return'] = df['Close'].pct_change().fillna(0)
    df['Equity'] = (1 + df['Strategy']).cumprod()
    df['BuyHold'] = (1 + df['Return']).cumprod()

    drawdown = (df['Equity'] / df['Equity'].cummax()) - 1

    # ======================
    # METRICAS
    # ======================
    st.subheader("Métricas")
    col1, col2, col3 = st.columns(3)

    col1.metric("Beta vs SPY", round(beta, 4))
    col2.metric("Retorno Estrategia", f"{df['Equity'].iloc[-1]:.2f}")
    col3.metric("Retorno Buy & Hold", f"{df['BuyHold'].iloc[-1]:.2f}")

    # ======================
    # GRAFICO PRECIO
    # ======================
    st.header("Gráfico de precios - SMA 20- SMA50 -B BOLINGER")
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name="Precio"
    ))

    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], name='SMA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name='SMA50'))

    fig.add_trace(go.Scatter(x=df.index, y=df['BB_UP'], name='BB Upper'))
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_LOW'], name='BB Lower'))

    st.plotly_chart(fig, use_container_width=True)

    # ======================
    # EQUITY CURVE
    # ======================
    st.header("Gráfico de evolución de BuyHold y Strategy")
    fig_eq = go.Figure()

    fig_eq.add_trace(go.Scatter(x=df.index, y=df['Equity'], name='Strategy'))
    fig_eq.add_trace(go.Scatter(x=df.index, y=df['BuyHold'], name='BuyHold'))

    st.plotly_chart(fig_eq, use_container_width=True)

    # ======================
    # DRAWDOWN
    # ======================
    st.header("Gráfico de evolución de Drawdown")
    fig_dd = go.Figure()

    fig_dd.add_trace(go.Scatter(x=df.index, y=drawdown, name='Drawdown'))

    st.plotly_chart(fig_dd, use_container_width=True)

    # ======================
    # MACD
    # ======================
    st.header("Gráfico de evolución de MACD")
    fig_macd = go.Figure()

    fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD'))
    fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD_SIGNAL'], name='Signal'))

    st.plotly_chart(fig_macd, use_container_width=True)

    # ======================
    # RSI
    # ======================
    st.header("Gráfico de evolución de RSI")
    fig_rsi = go.Figure()

    fig_rsi.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI'))

    st.plotly_chart(fig_rsi, use_container_width=True)

    # ======================
    # ATR
    # ======================
    st.header("Gráfico de evolución de ATR")
    fig_atr = go.Figure()

    fig_atr.add_trace(go.Scatter(x=df.index, y=df['ATR'], name='ATR'))

    st.plotly_chart(fig_atr, use_container_width=True)

    # ======================
    # BREAKOUT INDICATOR (RUST)
    # ======================

    high_list = df['High'].tolist()
    low_list = df['Low'].tolist()
    close_list = df['Close'].tolist()
    r_max, r_min, r_avg, scaled = oscilador.breakout_oscillator(high_list, low_list, close_list, n_breakout)

    #r_max, r_min, r_avg, scaled = oscilador.breakout_oscillator(high, low, close, n_breakout)
    b_signals = oscilador.breakout_signals(scaled, t1, t2)

    df['R_Max'] = r_max
    df['R_Min'] = r_min
    df['R_Avg'] = r_avg
    df['ScaledPrice'] = scaled
    df['B_Signals'] = b_signals

    # Agregamos los puntos para el gráfico
    def get_pointpos(row):
        if row['B_Signals'] == 2: return row['Low'] * 0.99
        if row['B_Signals'] == 1: return row['High'] * 1.01
        return None

    df['pointpos'] = df.apply(get_pointpos, axis=1)

    # ======================
    # GRAFICO BREAKOUT (NUEVO)
    # ======================
    st.subheader("Simple Break-Out Analysis")
    fig_bo = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Vela + Canales
    fig_bo.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Precio"), row=1, col=1)
    fig_bo.add_trace(go.Scatter(x=df.index, y=df['R_Max'], line=dict(color='#27F5F5', width=1), name="Max"), row=1, col=1)
    fig_bo.add_trace(go.Scatter(x=df.index, y=df['R_Min'], line=dict(color='#F5EE27', width=1), name="Min"), row=1, col=1)
    fig_bo.add_trace(go.Scatter(x=df.index, y=df['pointpos'], mode="markers", marker=dict(size=10, color="#F527C5", symbol="diamond"), name="Señal"), row=1, col=1)

    # Oscilador Inferior
    fig_bo.add_trace(go.Scatter(x=df.index, y=df['ScaledPrice'], line=dict(color='purple'), name="Scaled Price"), row=2, col=1)
    fig_bo.add_hline(y=t1, line_dash="dash", line_color="green", row=2, col=1)
    fig_bo.add_hline(y=t2, line_dash="dash", line_color="red", row=2, col=1)

    fig_bo.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig_bo, use_container_width=True)    
