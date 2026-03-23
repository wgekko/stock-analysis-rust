import pandas as pd
import numpy as np


def SMA(series, window=14):
    return series.rolling(window).mean()


def RSI(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def volatility(df, k_period=14, d_period=3):
    low_min = df['Low'].rolling(k_period).min()
    high_max = df['High'].rolling(k_period).max()
    k = 100 * (df['Close'] - low_min) / (high_max - low_min)
    d = k.rolling(d_period).mean()
    return k, d


def volatility(series, window=14):
    return series.pct_change().rolling(window).std() * np.sqrt(252)


def sharpe_ratio(series, rf=0.01):
    returns = series.pct_change().dropna()
    excess = returns - rf/252
    return (excess.mean() / excess.std()) * np.sqrt(252)


def signals(df):
    df['Signal'] = 0

    # RSI
    df.loc[df['RSI'] < 30, 'Signal'] += 1
    df.loc[df['RSI'] > 70, 'Signal'] -= 1

    # SMA crossover
    df.loc[df['SMA_20'] > df['SMA_50'], 'Signal'] += 1
    df.loc[df['SMA_20'] < df['SMA_50'], 'Signal'] -= 1

    return df


def backtest(df):
    df['Return'] = df['Close'].pct_change()
    df['Strategy'] = df['Signal'].shift(1) * df['Return']

    df['Equity'] = (1 + df['Strategy']).cumprod()
    df['BuyHold'] = (1 + df['Return']).cumprod()

    drawdown = (df['Equity'] / df['Equity'].cummax()) - 1

    win_rate = (df['Strategy'] > 0).mean()

    return df, drawdown, win_rate


def beta(asset, market):
    returns_a = asset.pct_change().dropna()
    returns_m = market.pct_change().dropna()

    cov = np.cov(returns_a, returns_m)[0][1]
    var = np.var(returns_m)

    return cov / var


def sharpe_ratio(series, rf=0.01):
    returns = series.pct_change().dropna()
    excess = returns - rf/252
    return (excess.mean() / excess.std()) * np.sqrt(252)


def beta(asset, market):
    returns_a = asset.pct_change().dropna()
    returns_m = market.pct_change().dropna()
    cov = np.cov(returns_a, returns_m)[0][1]
    var = np.var(returns_m)
    return cov / var
