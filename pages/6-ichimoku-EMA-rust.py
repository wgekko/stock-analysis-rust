import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pandas_datareader import data as pdr
import datetime
from backtesting import Backtest, Strategy

# Intentar importar el motor acelerado
try:
    import oscilador
except ImportError:
    st.error("Motor 'oscilador' no detectado. Revisa la instalación de Rust.")

# ==========================================
# LÓGICA DE INDICADORES (ICHIMOKU)
# ==========================================
def add_ichimoku_rust_compatible(df, tenkan=9, kijun=26, senkou_b=52):
    out = df.copy()
    high, low = out.High, out.Low
    
    out['ich_tenkan'] = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    out['ich_kijun'] = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    out['ich_spanA'] = (out['ich_tenkan'] + out['ich_kijun']) / 2
    out['ich_spanB'] = (high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2
    
    out['cloud_top'] = out[['ich_spanA', 'ich_spanB']].max(axis=1)
    out['cloud_bot'] = out[['ich_spanA', 'ich_spanB']].min(axis=1)
    return out

# ==========================================
# ESTRATEGIA
# ==========================================
class IchimokuEmaRustStrategy(Strategy):
    atr_mult_sl = 2.0
    rr_mult_tp = 3.0

    def init(self):
        self.signal = self.I(lambda x: x, self.data.signal)

    def next(self):
        price = self.data.Close[-1]
        atr = self.data.ATR[-1]
        if self.position or atr <= 0: return

        sl_dist = atr * self.atr_mult_sl
        tp_dist = sl_dist * self.rr_mult_tp

        if self.signal == 1:
            self.buy(sl=price - sl_dist, tp=price + tp_dist)
        elif self.signal == -1:
            self.sell(sl=price + sl_dist, tp=price - tp_dist)

# ==========================================
# UI DE STREAMLIT
# ==========================================
st.set_page_config(layout="wide", page_title="Ichimoku Rust Engine", page_icon=":material/stacked_line_chart:")
st.header(":material/stacked_line_chart: Ichimoku + EMA: Análisis Estrategia")

with st.container(border=True):
    # --- CAMBIO AQUÍ: Entrada simplificada ---
    user_ticker = st.text_input("Ticker (Ej: AMD, TSLA, NVDA)", "AMD").strip().upper()
    
    # Lógica para autocompletar el sufijo de Stooq
    if user_ticker and not user_ticker.endswith(".US"):
        ticker_stooq = f"{user_ticker}.US"
    else:
        ticker_stooq = user_ticker

    start_date = st.date_input("Fecha de Inicio", datetime.date(2022, 1, 1))
    st.info(f"Buscando en Stooq cotizacion : **{user_ticker}**")
    
    st.divider()
    ema_period = st.number_input("Filtro EMA Tendencia", value=100)
    atr_period = st.number_input("Periodo ATR (Riesgo)", value=14)

# ==========================================
# EJECUCIÓN
# ==========================================
if st.button("Lanzar Análisis"):
    try:
        with st.spinner(f'Descargando cotizaciones de {ticker_stooq}...'):
            # El sort_index() es vital para que las medias móviles no den error
            df = pdr.DataReader(ticker_stooq, "stooq", start_date).sort_index()
        
        if df.empty:
            st.error(f"No se encontraron datos para {ticker_stooq}. Verifica el Ticker.")
        else:
            # 1. Cálculos en RUST
            closes = df.Close.tolist()
            highs = df.High.tolist()
            lows = df.Low.tolist()
            
            df['ATR'] = oscilador.atr(highs, lows, closes, int(atr_period))
            df['EMA'] = oscilador.ema_py(closes, int(ema_period))
            
            # 2. Ichimoku & Señales
            df = add_ichimoku_rust_compatible(df)
            
            # Lógica de señales (Cruce de Nube + Filtro EMA)
            df['ema_up'] = (df['Close'] > df['EMA'])
            df['ema_down'] = (df['Close'] < df['EMA'])
            
            df['signal'] = 0
            # Long: Precio cruza hacia arriba la parte superior de la nube + EMA Alcista
            long_cond = (df['Open'] < df['cloud_top']) & (df['Close'] > df['cloud_top']) & (df['ema_up'])
            # Short: Precio cruza hacia abajo la parte inferior de la nube + EMA Bajista
            short_cond = (df['Open'] > df['cloud_bot']) & (df['Close'] < df['cloud_bot']) & (df['ema_down'])
            
            df.loc[long_cond, 'signal'] = 1
            df.loc[short_cond, 'signal'] = -1
            df.dropna(inplace=True)

            # 3. Backtest
            bt = Backtest(df, IchimokuEmaRustStrategy, cash=100000, commission=.002)
            stats = bt.run()
            
            # 4. Visualización Interactiva
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="Precio"))
            fig.add_trace(go.Scatter(x=df.index, y=df.EMA, line=dict(color='cyan', width=1), name="EMA Filter"))
            
            # Nube Ichimoku
            fig.add_trace(go.Scatter(x=df.index, y=df.ich_spanA, line=dict(color='rgba(0,255,0,0.2)'), name="Span A"))
            fig.add_trace(go.Scatter(x=df.index, y=df.ich_spanB, line=dict(color='rgba(255,0,0,0.2)'), fill='tonexty', name="Cloud"))
            
            # Marcadores de Señal
            longs = df[df.signal == 1]
            shorts = df[df.signal == -1]
            fig.add_trace(go.Scatter(x=longs.index, y=longs.Low * 0.98, mode='markers', marker=dict(symbol='triangle-up', size=12, color='lime'), name='Compra'))
            fig.add_trace(go.Scatter(x=shorts.index, y=shorts.High * 1.02, mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='Venta'))
            
            fig.update_layout(height=700, template="plotly_dark", title=f"Análisis Técnico: {user_ticker}", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            st.divider()
            col1, col2 = st.columns([2, 2])

            # Estadísticas
            with col1:
                st.subheader(f"Métricas de Estrategia ({user_ticker})")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Retorno Total", f"{stats['Return [%]']:.2f}%")
                c2.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
                c3.metric("Profit Factor", f"{stats['Profit Factor']:.2f}")
                c4.metric("Sharpe Ratio", f"{stats['Sharpe Ratio']:.2f}")
            with col2:
                st.subheader("Resultados")
                st.write(f"Retorno Final: {stats['Return [%]']:.2f}%")
                st.write(f"Win Rate: {stats['Win Rate [%]']:.2f}%")
                st.write(f"Sharpe Ratio: {stats['Sharpe Ratio']:.2f}")
                st.dataframe(stats.iloc[:15])

    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")