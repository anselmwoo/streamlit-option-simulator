import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import date

# 设置页面
st.set_page_config(page_title="Option Strategy Simulator", layout="wide")

# 用户输入
symbol = st.sidebar.text_input("Enter Ticker", value="AMD")
expiry = st.sidebar.text_input("Option Expiry (YYYY-MM-DD)", value="2024-08-16")
invest_limit = st.sidebar.number_input("Max Cost ($)", value=100.0)
cost_per_trade = st.sidebar.number_input("Transaction Cost per Leg ($)", value=1.0)
simulations = st.sidebar.slider("Monte Carlo Simulations", 1000, 20000, 5000)
user_position = st.sidebar.text_area("User Holdings (e.g., CALL 110C +1, PUT 90P -1)")

# 拉取数据
data = yf.Ticker(symbol)
opt_chain = data.option_chain(expiry)
calls = opt_chain.calls.copy()
puts = opt_chain.puts.copy()

# 添加 Greeks 占位符（模拟）
calls['delta'] = np.random.uniform(0.3, 0.8, size=len(calls))
calls['gamma'] = np.random.uniform(0.01, 0.15, size=len(calls))
puts['delta'] = np.random.uniform(-0.8, -0.3, size=len(puts))
puts['gamma'] = np.random.uniform(0.01, 0.15, size=len(puts))

# 当前价格和蒙特卡洛模拟价格
today_price = data.history(period="1d")['Close'].iloc[-1]
mu, sigma = 0.0, 0.2
prices = np.random.normal(loc=today_price * (1 + mu), scale=today_price * sigma, size=simulations)

# 策略函数模板
def bull_call_spread(calls):
    res = []
    for i in range(len(calls)):
        for j in range(i+1, len(calls)):
            buy = calls.iloc[i]
            sell = calls.iloc[j]
            debit = buy['ask'] - sell['bid'] + 2 * cost_per_trade
            if debit <= 0 or debit > invest_limit:
                continue
            max_profit = sell['strike'] - buy['strike'] - debit
            breakeven = buy['strike'] + debit
            pnl = np.piecewise(prices,
                               [prices <= buy['strike'], (prices > buy['strike']) & (prices < sell['strike']), prices >= sell['strike']],
                               [lambda x: -debit, lambda x: x - buy['strike'] - debit, lambda x: max_profit])
            pos_prob = np.mean(pnl > 0)
            avg_return = np.mean(pnl / debit)
            res.append({
                'type': 'Bull Call Spread',
                'buy_strike': buy['strike'],
                'sell_strike': sell['strike'],
                'cost': debit,
                'max_profit': max_profit,
                'breakeven': breakeven,
                'delta_net': buy['delta'] - sell['delta'],
                'gamma_net': buy['gamma'] - sell['gamma'],
                'pnl': pnl,
                'pos_prob': pos_prob,
                'avg_return': avg_return,
                'legs': f"Buy {buy['strike']}C @ {buy['ask']}, Sell {sell['strike']}C @ {sell['bid']}"
            })
    return res

# 更多策略（示例）
def short_put(puts):
    res = []
    for _, row in puts.iterrows():
        credit = row['bid'] - cost_per_trade
        strike = row['strike']
        pnl = np.piecewise(prices,
                           [prices < strike, prices >= strike],
                           [lambda x: credit - (strike - x), lambda x: credit])
        res.append({
            'type': 'Short Put',
            'sell_strike': strike,
            'cost': -credit,
            'max_profit': credit,
            'breakeven': strike - credit,
            'delta_net': row['delta'],
            'gamma_net': row['gamma'],
            'pnl': pnl,
            'pos_prob': np.mean(pnl > 0),
            'avg_return': np.mean(pnl / abs(credit)),
            'legs': f"Sell {strike}P @ {row['bid']}"
        })
    return res

# 汇总策略
data_strategies = bull_call_spread(calls) + short_put(puts)
strategies_df = pd.DataFrame(data_strategies)

# 按平均收益筛选前5策略
strategies_df = strategies_df.sort_values(by='avg_return', ascending=False).head(5)

# 显示策略
st.title(f"Option Strategy Simulator for {symbol}")
st.write(f"**Underlying Price:** ${today_price:.2f}")

for i, row in strategies_df.iterrows():
    st.subheader(f"{row['type']} Strategy")
    st.markdown(f"- Legs: {row['legs']}")
    st.markdown(f"- Cost: ${row['cost']:.2f}")
    st.markdown(f"- Max Profit: ${row['max_profit']:.2f}")
    st.markdown(f"- Breakeven: ${row['breakeven']:.2f}")
    st.markdown(f"- Δ: {row['delta_net']:.2f}, Γ: {row['gamma_net']:.2f}")
    st.markdown(f"- Profit Probability: {row['pos_prob']*100:.1f}%")
    st.markdown(f"- Avg Return: {row['avg_return']*100:.1f}%")
    fig, ax = plt.subplots()
    ax.hist(row['pnl'], bins=50, color='skyblue')
    ax.set_title("P&L Distribution")
    ax.set_xlabel("Profit / Loss")
    ax.set_ylabel("Frequency")
    st.pyplot(fig)

# 组合管理（基础展示）
if user_position:
    st.subheader("User Holdings (Preview Only)")
    for line in user_position.split("\n"):
        st.markdown(f"- {line}")
