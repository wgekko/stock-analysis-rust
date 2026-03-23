import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pandas_datareader import data as pdr
import datetime

# Importamos tu motor de Rust compilado
import oscilador

# Configuración de página
st.set_page_config(page_title="Stock Analysis", layout="wide", page_icon=":material/waterfall_chart:")

st.subheader(":material/bwaterfall_chart: BREAKUT INDICATOR")

# ==========================================
# CONTAINER - CONFIGURACIÓN
# ==========================================
with st.container(border=True):
    ticker = st.text_input("Ticker de la acción (EEUU)", value="AMD")
    
    st.divider()
    st.subheader("Parámetros Breakout")
    n_breakout = st.number_input("Ventana (N)", value=25, min_value=2)
    t1 = st.slider("Threshold Buy (t1)", 0.0, 1.0, 0.5)
    t2 = st.slider("Threshold Sell (t2)", -1.0, 0.0, -0.5)
    
    st.divider()
    st.subheader("Parámetros RSI")
    rsi_period = st.slider("Periodo RSI", 5, 30, 14)

# ==========================================
# LÓGICA PRINCIPAL
# ==========================================
st.subheader(f"Análisis Técnico: {ticker}")

if st.button("Ejecutar Análisis"):
    try:
        # 1. Obtención de datos
        start_date = datetime.datetime(2023, 1, 1)
        end_date = datetime.datetime.now()
        
        with st.spinner('Descargando datos de Stooq...'):
            df = pdr.get_data_stooq(ticker, start_date, end_date)
        
        if df is None or df.empty:
            st.error("No se encontraron datos para ese ticker.")
        else:
            # Ordenar por fecha (Stooq suele devolverlo invertido)
            df = df.sort_index()

            # 2. Preparar listas para Rust (Evita NameError)
            high_list = df['High'].tolist()
            low_list = df['Low'].tolist()
            close_list = df['Close'].tolist()

            # 3. EJECUCIÓN MOTOR DE RUST (Cálculos en paralelo)
            with st.spinner('Ejecutando motor de Rust...'):
                # Breakout Indicator
                r_max, r_min, r_avg, scaled = oscilador.breakout_oscillator(
                    high_list, low_list, close_list, n_breakout
                )
                b_signals = oscilador.breakout_signals(scaled, t1, t2)

                # Otros indicadores (ejemplo RSI)
                rsi_vals = oscilador.rsi(close_list, rsi_period)

            # 4. Integrar resultados al DataFrame
            df['R_Max'] = r_max
            df['R_Min'] = r_min
            df['R_Avg'] = r_avg
            df['ScaledPrice'] = scaled
            df['B_Signals'] = b_signals
            df['RSI'] = rsi_vals

            # Lógica de puntos para señales visuales
            def get_pointpos(row):
                if row['B_Signals'] == 2: return row['Low'] * 0.98
                if row['B_Signals'] == 1: return row['High'] * 1.02
                return None
            
            df['pointpos'] = df.apply(get_pointpos, axis=1)

            # ==========================================
            # VISUALIZACIÓN - PLOTLY
            # ==========================================
            st.subheader("Gráfico de Canales y Señales Breakout")
            
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.05, 
                row_heights=[0.7, 0.3]
            )

            # Subplot 1: Velas y Canales
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], 
                low=df['Low'], close=df['Close'], name="Precio"
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['R_Max'], line=dict(color='#27F5F5', width=1), name="Techo (Max)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['R_Min'], line=dict(color='#F5EE27', width=1), name="Suelo (Min)"), row=1, col=1)
            
            # Señales de entrada
            fig.add_trace(go.Scatter(
                x=df.index, y=df['pointpos'], mode="markers", 
                marker=dict(size=10, color="#F527C5", symbol="diamond"), 
                name="Entrada (Señal)"
            ), row=1, col=1)

            # Subplot 2: Oscilador Scaled Price
            fig.add_trace(go.Scatter(
                x=df.index, y=df['ScaledPrice'], 
                line=dict(color='purple'), name="Scaled Price"
            ), row=2, col=1)
            
            fig.add_hline(y=t1, line_dash="dash", line_color="green", row=2, col=1)
            fig.add_hline(y=t2, line_dash="dash", line_color="red", row=2, col=1)

            fig.update_layout(
                height=800, 
                template="plotly_dark", 
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # Tabla de datos recientes
            st.subheader("Últimos registros calculados")
            st.dataframe(df.tail(10))

    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")

else:
    st.info("Configura los parámetros en el panel lateral y haz clic en 'Ejecutar Análisis'.")