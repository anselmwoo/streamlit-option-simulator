# app_yahoo.py

import streamlit as st
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Option Strategy Simulator")

# ----------------- 左侧栏输入 -----------------
st.sidebar.title("📊 Option Strategy Builder")

symbol = st.sidebar.text_input("输入股票代码", value="AAPL").upper()

try:
    ticker = yf.Ticker(symbol)
    expiration_dates = ticker.options
except:
    st.sidebar.error("❌ 无法获取该股票的期权数据，请确认代码是否正确")
    st.stop()

expiry = st.sidebar.selectbox("选择到期日", expiration_dates)

option_chain = ticker.option_chain(expiry)
calls = option_chain.calls
puts = option_chain.puts

strategy = st.sidebar.selectbox("选择策略类型", ["Bull Call Spread", "Bear Put Spread"])

# 选择执行价范围
strikes = calls['strike'].values
min_strike = float(np.min(strikes))
max_strike = float(np.max(strikes))

strike_range = st.sidebar.slider("选择执行价范围", float(min_strike), float(max_strike), (float(min_strike), float(max_strike)))

# ----------------- 策略构建逻辑 -----------------
def create_bull_call_spread(calls_df, low_strike, high_strike):
    long_call = calls_df[calls_df['strike'] == low_strike]
    short_call = calls_df[calls_df['strike'] == high_strike]
    if long_call.empty or short_call.empty:
        return None
    cost = long_call['ask'].values[0] - short_call['bid'].values[0]
    max_profit = high_strike - low_strike - cost
    max_loss = cost
    return {
        "type": "Bull Call Spread",
        "long_strike": low_strike,
        "short_strike": high_strike,
        "net_cost": cost,
        "max_profit": max_profit,
        "max_loss": max_loss
    }

# ----------------- 收益图 -----------------
def plot_pnl(strategy, spot_price_range):
    pnl = []
    for price in spot_price_range:
        if strategy["type"] == "Bull Call Spread":
            long = max(price - strategy["long_strike"], 0)
            short = max(price - strategy["short_strike"], 0)
            total = long - short - strategy["net_cost"]
            pnl.append(total)
    return pnl

# ----------------- 策略生成与展示 -----------------
st.title("🧠 Option Strategy Simulator (Yahoo 数据源)")
st.markdown(f"**标的：** `{symbol}`  **到期日：** `{expiry}`")

strikes_in_range = [s for s in strikes if strike_range[0] <= s <= strike_range[1]]
strikes_in_range = sorted(strikes_in_range)

selected_low = st.selectbox("选择买入执行价", strikes_in_range)
selected_high = st.selectbox("选择卖出执行价", [s for s in strikes_in_range if s > selected_low])

if strategy == "Bull Call Spread":
    result = create_bull_call_spread(calls, selected_low, selected_high)

    if result:
        spot_prices = np.linspace(selected_low - 10, selected_high + 10, 100)
        pnl = plot_pnl(result, spot_prices)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("💰 最大收益", f"${result['max_profit']:.2f}")
            st.metric("💸 最大亏损", f"${result['max_loss']:.2f}")
            st.metric("⚖️ 收益比", f"{result['max_profit'] / result['max_loss']:.2f} : 1")
        with col2:
            st.metric("🧾 净成本", f"${result['net_cost']:.2f}")
            st.metric("📍 盈亏平衡点", f"${result['long_strike'] + result['net_cost']:.2f}")

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(spot_prices, pnl, label="策略 PnL", color="blue")
        ax.axhline(0, linestyle='--', color='gray')
        ax.axvline(result['long_strike'], linestyle=':', color='green', label='买入 Call')
        ax.axvline(result['short_strike'], linestyle=':', color='red', label='卖出 Call')
        ax.set_title("📈 策略收益曲线")
        ax.set_xlabel("标的价格")
        ax.set_ylabel("盈亏 ($)")
        ax.legend()
        st.pyplot(fig)
    else:
        st.warning("❗ 当前执行价组合无有效价格，请重新选择")

