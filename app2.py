import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date

st.set_page_config(layout="wide")

# 获取期权链数据
def get_option_chain(symbol):
    stock = yf.Ticker(symbol)
    expirations = stock.options
    return stock, expirations

# 策略生成逻辑（简化示例）
def generate_strategies(options_chain, kind="call"):
    df = options_chain.copy()
    df = df[['strike', 'lastPrice', 'impliedVolatility']].dropna()
    df.columns = ['执行价', '期权价格', 'IV']
    strategies = []

    # 单腿策略：买入看涨期权
    for _, row in df.iterrows():
        strike = row['执行价']
        price = row['期权价格']
        iv = row['IV']
        strategy = {
            "策略类型": "买入看涨期权" if kind == "call" else "买入看跌期权",
            "买入执行价": strike,
            "卖出执行价": None,
            "成本": price,
            "最大收益": None,
            "最大亏损": price,
            "盈亏平衡点": strike + price if kind == "call" else strike - price
        }
        strategies.append(strategy)

    # 示例：牛市价差策略（买低卖高）
    for i in range(len(df) - 1):
        long_strike = df.iloc[i]['执行价']
        short_strike = df.iloc[i + 1]['执行价']
        long_price = df.iloc[i]['期权价格']
        short_price = df.iloc[i + 1]['期权价格']
        cost = long_price - short_price
        max_profit = short_strike - long_strike - cost
        strategy = {
            "策略类型": "牛市价差",
            "买入执行价": long_strike,
            "卖出执行价": short_strike,
            "成本": cost,
            "最大收益": max_profit,
            "最大亏损": cost,
            "盈亏平衡点": long_strike + cost
        }
        strategies.append(strategy)

    return pd.DataFrame(strategies)

# 收益绘图函数
def plot_payoff(strategy_row):
    st.subheader(f"策略收益图 - {strategy_row['策略类型']}")
    spot_prices = np.linspace(0.5 * strategy_row['买入执行价'], 1.5 * (strategy_row['卖出执行价'] or strategy_row['买入执行价']), 300)
    payoff = []

    cost = strategy_row["成本"]
    buy_strike = strategy_row["买入执行价"]
    sell_strike = strategy_row["卖出执行价"]

    for S in spot_prices:
        if strategy_row["策略类型"] == "买入看涨期权":
            payoff.append(max(S - buy_strike, 0) - cost)
        elif strategy_row["策略类型"] == "买入看跌期权":
            payoff.append(max(buy_strike - S, 0) - cost)
        elif strategy_row["策略类型"] == "牛市价差":
            leg1 = max(S - buy_strike, 0)
            leg2 = max(S - sell_strike, 0)
            payoff.append(leg1 - leg2 - cost)
        else:
            payoff.append(0)

    fig, ax = plt.subplots()
    ax.plot(spot_prices, payoff, label='策略收益', color='blue')
    ax.axhline(0, color='gray', linestyle='--')
    ax.set_xlabel("标的价格")
    ax.set_ylabel("收益")
    ax.set_title("期权策略收益曲线")
    ax.grid(True)
    st.pyplot(fig)

# Streamlit 界面
st.title("期权策略模拟器")

with st.sidebar:
    symbol = st.text_input("输入标的代码 (如 AMD)", value="AMD").upper()

# 获取期权数据
if symbol:
    try:
        stock, expirations = get_option_chain(symbol)
        st.sidebar.success(f"成功获取 {symbol} 期权数据")
        expiry = st.selectbox("选择到期日", expirations)

        if expiry:
            chain = stock.option_chain(expiry)
            kind = st.radio("选择期权类型", ["call", "put"])
            options_chain = chain.calls if kind == "call" else chain.puts
            strategy_df = generate_strategies(options_chain, kind=kind)

            st.subheader("策略选择")
            selected_row = st.data_editor(
                strategy_df,
                use_container_width=True,
                hide_index=True,
                column_order=("策略类型", "买入执行价", "卖出执行价", "成本", "最大收益", "最大亏损", "盈亏平衡点"),
                num_rows="dynamic",
                key="strategy_table"
            )

            if isinstance(selected_row, list) and len(selected_row) > 0:
                selected_index = selected_row[0]
                selected_strategy = strategy_df.iloc[selected_index]
                plot_payoff(selected_strategy)
    except Exception as e:
        st.error(f"加载失败：{e}")
