import streamlit as st
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(layout="wide")
st.title("期权策略模拟器 with 策略筛选、交易成本 & 风险分析")

# 用户输入标的股票代码
symbol = st.text_input("输入标的股票代码 (如 AMD)", value="AMD").upper()
data = yf.Ticker(symbol)

# 显示可选的期权到期日
try:
    available_expirations = data.options
    expiry = st.selectbox("选择期权到期日", available_expirations)
except Exception as e:
    st.error("未找到该股票的期权链，请确认股票代码是否正确")
    st.stop()

# 获取期权链数据
try:
    opt_chain = data.option_chain(expiry)
    calls = opt_chain.calls
    puts = opt_chain.puts
except ValueError as ve:
    st.error(str(ve))
    st.stop()

# 显示期权链数据
with st.expander("📄 Call期权链"):
    st.dataframe(calls[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility', 'delta', 'gamma']])

with st.expander("📄 Put期权链"):
    st.dataframe(puts[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility', 'delta', 'gamma']])

# 用户输入现有持仓
st.sidebar.subheader("📊 持仓信息")
position_type = st.sidebar.selectbox("持仓类型", ["无持仓", "持有正股", "持有期权"])
cost_basis = st.sidebar.number_input("成本价", value=0.0)
shares_held = st.sidebar.number_input("持仓数量", value=0, step=1)

# 模拟策略
st.sidebar.subheader("📈 策略选择")
strategy = st.sidebar.selectbox("选择策略", ["Bull Call Spread", "Sell Put", "Sell Call"])

# 显示交易成本
commission = st.sidebar.number_input("每笔交易手续费($)", value=1.0)

# 策略函数

def bull_call_spread(calls):
    calls_sorted = calls.sort_values("strike")
    if len(calls_sorted) < 2:
        st.warning("Bull Call Spread需要至少两个不同执行价的Call期权")
        return None
    
    buy = calls_sorted.iloc[0]
    sell = calls_sorted.iloc[-1]
    debit = buy.ask - sell.bid
    max_profit = sell.strike - buy.strike - debit
    
    prices = np.linspace(buy.strike * 0.9, sell.strike * 1.1, 100)
    pnl = np.piecewise(prices,
                       [prices <= buy.strike,
                        (prices > buy.strike) & (prices < sell.strike),
                        prices >= sell.strike],
                       [-debit, lambda x: x - buy.strike - debit, max_profit])
    return prices, pnl

def sell_put(puts):
    puts_sorted = puts.sort_values("strike")
    sell = puts_sorted.iloc[0]
    strike = sell.strike
    premium = sell.bid
    
    prices = np.linspace(strike * 0.8, strike * 1.2, 100)
    pnl = np.where(prices >= strike, premium, premium - (strike - prices))
    return prices, pnl

def sell_call(calls):
    calls_sorted = calls.sort_values("strike")
    sell = calls_sorted.iloc[-1]
    strike = sell.strike
    premium = sell.bid
    
    prices = np.linspace(strike * 0.8, strike * 1.2, 100)
    pnl = np.where(prices <= strike, premium, premium - (prices - strike))
    return prices, pnl

# 执行策略模拟
result = None
if strategy == "Bull Call Spread":
    result = bull_call_spread(calls)
elif strategy == "Sell Put":
    result = sell_put(puts)
elif strategy == "Sell Call":
    result = sell_call(calls)

# 可视化结果
if result:
    prices, pnl = result
    fig, ax = plt.subplots()
    ax.plot(prices, pnl, label=strategy)
    ax.axhline(0, color='gray', linestyle='--')
    ax.set_xlabel("标的价格")
    ax.set_ylabel("收益 ($)")
    ax.set_title(f"策略盈亏图 - {strategy}")
    ax.legend()
    st.pyplot(fig)

# 显示模拟结果表格
if result:
    df_result = pd.DataFrame({"标的价格": prices, "策略盈亏": pnl})
    with st.expander("📊 策略模拟结果明细"):
        st.dataframe(df_result.round(2))

# 模拟提示
st.info("后续可添加更多策略、蒙特卡洛模拟与风险参数评估（IV、Delta等），并支持组合持仓管理")
