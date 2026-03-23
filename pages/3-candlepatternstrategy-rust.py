import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pandas_datareader import data as pdr
from backtesting import Strategy, Backtest
import datetime

# Intentar importar el motor de Rust
try:
    import oscilador
except ImportError:
    st.error("No se detectó el módulo 'oscilador'. Ejecuta 'maturin develop' en la carpeta rust_engine.")

# Configuración de página
st.set_page_config(layout="wide", page_title="Candle Pattern Strategy", page_icon=":material/strategy:")
st.header(":material/strategy: Candle Pattern Strategy")

# ==========================================
# ESTRATEGIA PARA BACKTESTING.PY
# ==========================================
class DailyBiasStrat(Strategy):
    def init(self):
        super().init()
        # El indicador es la señal calculada previamente
        self.daily_sig = self.I(lambda: self.data.DailySignal)

    def next(self):
        # Lógica de salida: Si Exit es 1, cerramos posición
        if self.data.Exit[-1] == 1:
            for trade in self.trades:
                trade.close()

        # Lógica de entrada
        if not self.position:
            # Compra: Bias 2 (alcista) y tenemos un StopPrice válido
            if self.daily_sig[-1] == 2 and self.data.StopPrice[-1] > 0:
                self.buy(stop=self.data.StopPrice[-1])
            
            # Venta: Bias 1 (bajista) y tenemos un StopPrice válido
            elif self.daily_sig[-1] == 1 and self.data.StopPrice[-1] > 0:
                self.sell(stop=self.data.StopPrice[-1])

# ======================
# CONTAINER
# ======================
with st.container(border=True):
    st.subheader(":material/settings_alert: Configuración")
    ticker = st.text_input("Ticker", "AMD")
    start = st.date_input("Inicio", datetime.date(2023, 1, 1))
    end = st.date_input("Fin", datetime.date.today())
    st.divider()
    test_candles = st.slider("Velas de Rango (n)", 1, 10, 2)
    exit_delay = st.slider("Días de salida", 1, 5, 1)

# ======================
# LÓGICA DE EJECUCIÓN
# ======================
if st.button("Ejecutar Backtest Acelerado"):
    try:
        with st.spinner('Descargando datos de Stooq...'):
            df = pdr.DataReader(ticker, "stooq", start, end).sort_index()

        if df.empty:
            st.error("No se encontraron datos.")
        else:
            # --- 1. PREPARACIÓN DE LISTAS (Formato para Rust) ---
            close_l = df['Close'].values.tolist()
            high_l = df['High'].values.tolist()
            low_l = df['Low'].values.tolist()
            open_l = df['Open'].values.tolist()

            # --- 2. CÁLCULO CON RUST ---
            with st.spinner('Calculando señales en Rust...'):
                # Usamos breakout_oscillator para obtener los niveles máximos y mínimos
                # de forma paralela, reemplazando el bucle 'for' de Python.
                r_max, r_min, _, _ = oscilador.breakout_oscillator(
                    high_l, low_l, close_l, test_candles
                )
                
                # Calculamos el RSI también en Rust por si quieres usarlo como filtro
                df['RSI'] = oscilador.rsi(close_l, 14)

            # --- 3. LÓGICA DE SEÑALES (Vectorizada) ---
            # Bias: 2 si cerró verde ayer, 1 si cerró rojo ayer
            df['DailySignal'] = np.where(df['Close'] > df['Open'], 2, 1)
            df['DailySignal'] = df['DailySignal'].shift(1)

            # Precios de ejecución: Si el bias es alcista, entramos al romper el máximo
            # del rango previo (r_max). Si es bajista, al romper el mínimo (r_min).
            df['StopPrice'] = np.where(df['DailySignal'] == 2, r_max, r_min)
            
            # Definir salida
            df['Exit'] = 0
            df.loc[df.index[exit_delay:], 'Exit'] = 1

            df_final = df.dropna(subset=['DailySignal', 'StopPrice']).copy()

            # --- 4. BACKTEST ---
            bt = Backtest(df_final, DailyBiasStrat, cash=10000, commission=.001)
            stats = bt.run()

            # --- 5. VISUALIZACIÓN ---
            st.subheader(f"Resultados de Backtest: {ticker}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Retorno Total", f"{stats['Return [%]']:.2f}%")
            c2.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
            c3.metric("Nº Operaciones", stats['# Trades'])

            # Gráfico de Equidad (Curva de ganancias)
            st.subheader(":material7trending_up: Curva de Equidad")
            st.line_chart(stats['_equity_curve']['Equity'])

            # Gráfico de Velas Japonesas e Indicadores
            st.subheader(":material/chart_data: Análisis Visual")
            fig = go.Figure(data=[go.Candlestick(
                x=df_final.index, open=df_final.Open, high=df_final.High, 
                low=df_final.Low, close=df_final.Close, name="Precio"
            )])
            
            # Dibujamos los StopPrices calculados por Rust
            fig.add_trace(go.Scatter(
                x=df_final.index, y=df_final.StopPrice, 
                mode="markers", name="Nivel de Entrada (Rust)",
                marker=dict(color="cyan", size=5, symbol="x")
            ))

            fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- 6. LISTAS DE DATOS (Lo que pediste) ---
            with st.expander(":material/list_alt_check: Ver Listas de Datos (Formato compatible Rust/Python)"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write("**Close List (Primeros 10):**")
                    st.json(close_l[:10])
                with col_b:
                    st.write("**DataFrame Final (Últimas filas):**")
                    st.dataframe(df_final.tail())

    except Exception as e:
        st.error(f"Error técnico: {e}")