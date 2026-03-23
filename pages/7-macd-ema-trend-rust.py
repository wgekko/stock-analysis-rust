import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pandas_datareader import data as pdr
import datetime
from backtesting import Backtest, Strategy

# Intentar importar tu módulo de Rust
try:
    import oscilador
except ImportError:
    st.error(":material/warning: No se encontró el módulo 'oscilador'. Asegúrate de haber compilado el archivo lib.rs.")

# ==========================================
# PROCESAMIENTO CON RUST
# ==========================================
def apply_rust_indicators(df, back_trend=5):
    # Convertir columnas a listas de floats para Rust
    close_list = df['Close'].tolist()
    open_list = df['Open'].tolist()
    high_list = df['High'].tolist()
    low_list = df['Low'].tolist()

    # 1. EMA 200 usando tu función ema_py
    df['EMA200'] = oscilador.ema_py(close_list, 200)

    # 2. MACD (12, 26, 9) usando tu función macd
    m_line, s_line, h_line = oscilador.macd(close_list)
    df['MACD'], df['MACD_S'], df['MACD_H'] = m_line, s_line, h_line

    # 3. Filtro de Tendencia EMA usando tu función ema_trend_filter
    # Devuelve: 2 (Up), 1 (Down), 0 (None)
    ema_list = df['EMA200'].tolist()
    df['trend_sig'] = oscilador.ema_trend_filter(open_list, close_list, ema_list, back_trend)

    # 4. ATR para el Stop Loss
    df['ATR'] = oscilador.atr(high_list, low_list, close_list, 14)

    # 5. Lógica de Señal Final (Python coordina los resultados de Rust)
    df['pre_signal'] = 0
    
    # Cruces de MACD (Lógica de soporte)
    macd_cross_up = (df['MACD'].shift(1) <= df['MACD_S'].shift(1)) & (df['MACD'] > df['MACD_S'])
    macd_cross_down = (df['MACD'].shift(1) >= df['MACD_S'].shift(1)) & (df['MACD'] < df['MACD_S'])

    # Condición Long: Tendencia Alcista (2) + MACD Cross Up < 0
    long_mask = (df['trend_sig'] == 2) & macd_cross_up & (df['MACD'] < 0)
    # Condición Short: Tendencia Bajista (1) + MACD Cross Down > 0
    short_mask = (df['trend_sig'] == 1) & macd_cross_down & (df['MACD'] > 0)

    df.loc[long_mask, 'pre_signal'] = 1
    df.loc[short_mask, 'pre_signal'] = -1
    
    return df

# ==========================================
# ESTRATEGIA (Swing Window + Break Even)
# ==========================================
class MacdEmaRustStrategy(Strategy):
    rr = 1.5
    sw_window = 5

    def init(self):
        self._moved_be = False
        self.sig = self.I(lambda x: x, self.data.df.pre_signal)

    def next(self):
        price = self.data.Close[-1]
        
        if not self.position:
            self._moved_be = False
            # Ventana de Swing usando los datos actuales
            window_lows = self.data.Low[-self.sw_window:]
            window_highs = self.data.High[-self.sw_window:]

            if self.sig == 1:
                sl = min(window_lows)
                dist = price - sl
                if dist > 0: self.buy(sl=sl, tp=price + self.rr * dist)
                
            elif self.sig == -1:
                sl = max(window_highs)
                dist = sl - price
                if dist > 0: self.sell(sl=sl, tp=price - self.rr * dist)
        else:
            # Lógica de Break-Even (Mover SL al precio de entrada)
            tr = self.trades[0]
            risk = abs(tr.entry_price - tr.sl)
            if not self._moved_be:
                if tr.is_long and (price - tr.entry_price) >= risk:
                    tr.sl = tr.entry_price
                    self._moved_be = True
                elif tr.is_short and (tr.entry_price - price) >= risk:
                    tr.sl = tr.entry_price
                    self._moved_be = True

# ==========================================
# UI - STREAMLIT
# ==========================================
st.set_page_config(layout="wide", page_title="MACD EMA TREND", page_icon=":material/tactic:")
st.header(":material/tactic: Sistema EMA + MACD trend")

with st.container(border=True):
    st.subheader(":material/settings_alert: Configuración")
    # Lógica de Ticker sugerida anteriormente
    u_ticker = st.text_input("Ticker de Acción", "AMD").strip().upper()
    ticker_stooq = f"{u_ticker}.US" if not u_ticker.endswith(".US") else u_ticker
    
    st.info(f"Buscando en Stooq: {u_ticker}")
    
    start_date = st.date_input("Fecha Inicio", datetime.date(2023, 1, 1))
    st.divider()
    rr_param = st.slider("Risk/Reward Ratio", 1.0, 4.0, 1.5, 0.1)
    sw_param = st.slider("Swing Window (Velas)", 2, 10, 5)

if st.button("Ejecutar Análisis"):
    try:
        with st.spinner("Consultando Stooq y procesando en Rust..."):
            df = pdr.DataReader(ticker_stooq, "stooq", start_date).sort_index()
            
        if df.empty:
            st.warning("No se encontraron datos.")
        else:
            # Ejecutar lógica de Rust
            df = apply_rust_indicators(df)
            
            # Backtest
            MacdEmaRustStrategy.rr = rr_param
            MacdEmaRustStrategy.sw_window = sw_param
            bt = Backtest(df, MacdEmaRustStrategy, cash=100_000, commission=0.001)
            stats = bt.run()
            
            # --- DASHBOARD ---
            c1, c2, c3 = st.columns(3)
            c1.metric("Retorno", f"{stats['Return [%]']:.2f}%")
            c2.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
            c3.metric("Trades Totales", int(stats['# Trades']))

            # Gráfico interactivo
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            
            # Precio y Señales
            fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df.EMA200, line=dict(color='orange', width=1.5), name="EMA 200"), row=1, col=1)
            
            # Marcar Compras/Ventas
            longs = df[df.pre_signal == 1]
            shorts = df[df.pre_signal == -1]
            fig.add_trace(go.Scatter(x=longs.index, y=longs.Low * 0.99, mode='markers', marker=dict(symbol='triangle-up', size=12, color='lime'), name='Buy Sig'), row=1, col=1)
            fig.add_trace(go.Scatter(x=shorts.index, y=shorts.High * 1.01, mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='Sell Sig'), row=1, col=1)
            
            # MACD
            fig.add_trace(go.Bar(x=df.index, y=df.MACD_H, name="Histog", marker_color='rgba(100, 100, 100, 0.5)'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df.MACD, line=dict(color='cyan', width=1), name="MACD"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df.MACD_S, line=dict(color='magenta', width=1), name="Signal"), row=2, col=1)
            
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            #st.text(stats)
            # Tabla de estadísticas completa centrada           
            #_, center_table, _ = st.columns([1, 3, 1])
            #with center_table:
            #    st.write("### Detalle Estadístico")
            #    st.dataframe(stats.to_frame(), use_container_width=True)

            col1, col2 = st.columns([2,2])
            # Estadísticas
            with col1:    
                st.write("### Detalle Estadístico")
                st.text(stats, text_alignment="center", width="stretch")          
            with col2:    
                st.write("### Detalle Estadístico")
                st.dataframe(stats.to_frame(), width="stretch", use_container_width=True)
                

    except Exception as e:
        st.error(f"Error: {e}")