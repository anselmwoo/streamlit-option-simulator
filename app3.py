import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import datetime

st.set_page_config(layout="wide")
st.title("期权策略模拟器（支持多策略组合分析）")

# ------------------------- 获取用户输入 -------------------------
st.sidebar.header("选择参数")
ticker = st.sidebar.text_input("输入股票代码 (如 AMD):", value="AMD")

try:
    stock = yf.Ticker(ticker)
    current_price = stock.history(period="1d")["Close"].iloc[-1]
    options_dates = stock.options
except:
    st.error("获取标的信息失败，请检查代码是否正确。")
    st.stop()

exp_date = st.sidebar.selectbox("选择到期日:", options_dates)
min_strike = st.sidebar.number_input("最小执行价", value=int(current_price * 0.5))
max_strike = st.sidebar.number_input("最大执行价", value=int(current_price * 1.5))

# ------------------------- 获取期权链 -------------------------
opt_chain = stock.option_chain(exp_date)
call_df = opt_chain.calls.copy()
put_df = opt_chain.puts.copy()

# 过滤价格范围
call_df = call_df[(call_df["strike"] >= min_strike) & (call_df["strike"] <= max_strike)]
put_df = put_df[(put_df["strike"] >= min_strike) & (put_df["strike"] <= max_strike)]

st.subheader(f"Call / Put 期权链数据 - 到期日: {exp_date}")
st.dataframe(pd.concat([call_df[['strike', 'bid', 'ask', 'impliedVolatility']].rename(columns={'bid': 'Call Bid', 'ask': 'Call Ask', 'impliedVolatility': 'Call IV'}),
                        put_df[['strike', 'bid', 'ask', 'impliedVolatility']].rename(columns={'bid': 'Put Bid', 'ask': 'Put Ask', 'impliedVolatility': 'Put IV'})],
                       axis=1))

# ------------------------- 策略模拟 -------------------------
st.subheader("策略收益模拟与评分")
def simulate_strategy(s, k1, k2, option_type, cost):
    # s: spot price
    # k1: 买入价，k2: 卖出价
    prices = np.linspace(s * 0.5, s * 1.5, 100)
    if option_type == "Bull Call Spread":
        payoff = np.maximum(prices - k1, 0) - np.maximum(prices - k2, 0) - cost
    elif option_type == "Bear Put Spread":
        payoff = np.maximum(k2 - prices, 0) - np.maximum(k1 - prices, 0) - cost
    elif option_type == "Covered Call":
        payoff = np.minimum(k1 - s, 0) + np.minimum(np.maximum(prices - k1, 0), k1 - s)
    else:
        payoff = np.zeros_like(prices)
    return prices, payoff

# 遍历生成 Bull Call Spread 组合
strategies = []
for i in range(len(call_df)):
    for j in range(i + 1, len(call_df)):
        k1, k2 = call_df.iloc[i]['strike'], call_df.iloc[j]['strike']
        buy_cost = (call_df.iloc[i]['ask'] + call_df.iloc[i]['bid']) / 2
        sell_credit = (call_df.iloc[j]['ask'] + call_df.iloc[j]['bid']) / 2
        net_cost = buy_cost - sell_credit
        prices, payoff = simulate_strategy(current_price, k1, k2, "Bull Call Spread", net_cost)
        max_profit = np.max(payoff)
        prob_profit = norm.cdf((k2 - current_price) / (current_price * 0.2))  # 简单估算
        score = max_profit / net_cost if net_cost > 0 else 0
        strategies.append({
            "策略": f"Buy {k1}C / Sell {k2}C",
            "类型": "Bull Call Spread",
            "成本": round(net_cost, 2),
            "最大收益": round(max_profit, 2),
            "盈利概率": f"{prob_profit * 100:.1f}%",
            "得分": round(score, 2),
            "图": (prices, payoff)
        })

strategy_df = pd.DataFrame(strategies)
st.dataframe(strategy_df.sort_values("得分", ascending=False).reset_index(drop=True))

selected_idx = st.selectbox("选择策略查看收益图:", strategy_df.index, format_func=lambda i: strategy_df.loc[i, "策略"])

# ------------------------- 绘制图表 -------------------------
fig, ax = plt.subplots(figsize=(10, 4))
plot_prices, plot_payoff = strategy_df.loc[selected_idx, "图"]
ax.plot(plot_prices, plot_payoff, label=strategy_df.loc[selected_idx, "策略"])
ax.axvline(current_price, color='r', linestyle='--', label='现价')
ax.set_xlabel("股价")
ax.set_ylabel("收益")
ax.set_title("策略收益曲线")
ax.legend()
st.pyplot(fig)

# ------------------------- 未来计划 -------------------------
st.markdown("""
**📌 后续功能规划：**
- 支持更多策略类型（Iron Condor、Straddle 等）
- 更精细的希腊值计算与Delta-Gamma可视化
- 支持导入持仓、进行组合风险敞口分析
- 自动推荐最优策略
""")
