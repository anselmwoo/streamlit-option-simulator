import streamlit as st
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

# Tradier API
TRADIER_TOKEN = 'YOUR_TRADIER_API_KEY'
HEADERS = {'Authorization': f'Bearer {TRADIER_TOKEN}', 'Accept': 'application/json'}
BASE_URL = 'https://api.tradier.com/v1/markets/options'

# 设置页面布局
st.set_page_config(page_title="Option Strategy Simulator", layout="wide")

# 侧栏：标的与到期日
st.sidebar.title("📈 Option Strategy Simulator")
symbol = st.sidebar.text_input("Symbol", value="AMD").upper()

# 拉取可用到期日
@st.cache_data(show_spinner=False)
def get_expirations(symbol):
    url = f"{BASE_URL}/expirations"
    params = {"symbol": symbol, "includeAllRoots": "true", "strikes": "false"}
    r = requests.get(url, headers=HEADERS, params=params)
    data = r.json()
    return data['expirations']['date'] if 'expirations' in data else []

expirations = get_expirations(symbol)
if not expirations:
    st.error("Failed to fetch expirations.")
    st.stop()

expiration = st.sidebar.selectbox("Expiration Date", expirations)

# 拉取期权链
@st.cache_data(show_spinner=False)
def get_option_chain(symbol, expiration):
    url = f"{BASE_URL}/chains"
    params = {"symbol": symbol, "expiration": expiration, "greeks": "true"}
    r = requests.get(url, headers=HEADERS, params=params)
    data = r.json()
    if "options" not in data or not data["options"]:
        return pd.DataFrame()
    options = data["options"]["option"]
    return pd.DataFrame(options)

df = get_option_chain(symbol, expiration)
if df.empty:
    st.error("No options data found.")
    st.stop()

# 拆分 call/put，修复重复列问题
call_df = df[df['option_type'] == 'call'].copy()
put_df = df[df['option_type'] == 'put'].copy()

# 保证唯一 strike
merged = pd.merge(
    call_df[['strike', 'bid', 'ask', 'implied_volatility']].rename(
        columns={'bid': 'Call Bid', 'ask': 'Call Ask', 'implied_volatility': 'Call IV'}
    ),
    put_df[['strike', 'bid', 'ask', 'implied_volatility']].rename(
        columns={'bid': 'Put Bid', 'ask': 'Put Ask', 'implied_volatility': 'Put IV'}
    ),
    on='strike', how='outer'
).sort_values(by='strike')

st.subheader(f"{symbol} Option Chain for {expiration}")
st.dataframe(merged, use_container_width=True)

# 计算当前股价（近月 ATM）
atm_strike = df.iloc[df['strike'].sub(float(df['last'])).abs().idxmin()]['strike']
spot_price = float(df[df['strike'] == atm_strike].iloc[0]['last'])

# 策略生成示例（Covered Call）
def simulate_covered_call(call_row, spot):
    call_strike = call_row['strike']
    call_bid = call_row['bid']
    payoff = []

    prices = np.linspace(spot * 0.7, spot * 1.3, 100)
    for price in prices:
        stock_pnl = price - spot
        option_pnl = -max(price - call_strike, 0) + call_bid
        payoff.append(stock_pnl + option_pnl)

    return prices, payoff

st.subheader("🧠 Strategy Simulation")
strategy_type = st.selectbox("Strategy Type", ["Covered Call", "Protective Put", "Iron Condor (Coming Soon)"])

# 自动选择几组执行价
strategies = []

if strategy_type == "Covered Call":
    filtered_calls = call_df[(call_df['strike'] > spot_price * 0.95) & (call_df['strike'] < spot_price * 1.1)].copy()
    filtered_calls = filtered_calls.sort_values('strike')

    for _, row in filtered_calls.iterrows():
        prices, payoff = simulate_covered_call(row, spot_price)
        mean_pnl = np.mean(payoff)
        std_pnl = np.std(payoff)
        sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0
        strategies.append({
            'Strategy': f'Covered Call @ {row["strike"]}',
            'Call Strike': row['strike'],
            'Call Bid': row['bid'],
            'Mean PnL': round(mean_pnl, 2),
            'Sharpe': round(sharpe, 2),
            'Prices': prices,
            'Payoff': payoff
        })

if strategies:
    strat_df = pd.DataFrame(strategies).drop(columns=['Prices', 'Payoff'])
    selected = st.selectbox("Select Strategy to Visualize", strat_df['Strategy'])
    st.dataframe(strat_df, use_container_width=True)

    # 画图
    for strat in strategies:
        if strat['Strategy'] == selected:
            fig, ax = plt.subplots()
            ax.plot(strat['Prices'], strat['Payoff'], label=selected, color='blue')
            ax.axhline(0, linestyle='--', color='gray')
            ax.set_title(f"Payoff Diagram: {selected}")
            ax.set_xlabel("Underlying Price at Expiry")
            ax.set_ylabel("Profit / Loss")
            st.pyplot(fig)

            # 模拟价格概率分布（正态近似）
            fig2, ax2 = plt.subplots()
            price_range = np.linspace(spot_price * 0.7, spot_price * 1.3, 100)
            mu, sigma = spot_price, spot_price * 0.2  # 假设波动率 20%
            prob = norm.pdf(price_range, mu, sigma)
            prob = prob / prob.sum()  # 归一化

            expected = np.array(strat['Payoff']) * prob
            expected_return = expected.sum()

            ax2.plot(strat['Prices'], strat['Payoff'], label="Payoff", color='blue')
            ax2.fill_between(strat['Prices'], 0, prob * max(strat['Payoff']), color='orange', alpha=0.3, label="Price Probability")
            ax2.set_title("Profit & Probability Distribution")
            ax2.legend()
            st.pyplot(fig2)
            st.success(f"Expected Return (Prob-Weighted): ${expected_return:.2f}")
