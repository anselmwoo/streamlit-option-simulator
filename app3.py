import streamlit as st
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(layout="wide", page_title="Options Strategy Simulator")

# ----------------- 左侧栏输入 -----------------
st.sidebar.title("📊 Option Strategy Builder")

symbol = st.sidebar.text_input("Enter stock symbol", value="AAPL").upper()

try:
    ticker = yf.Ticker(symbol)
    expiration_dates = ticker.options
except Exception:
    st.sidebar.error("❌ Unable to fetch option data for the symbol")
    st.stop()

expiry = st.sidebar.selectbox("Select expiration date", expiration_dates)

option_chain = ticker.option_chain(expiry)
calls = option_chain.calls
puts = option_chain.puts

# Filter strike price range for user convenience
strikes = sorted(set(calls['strike']).intersection(set(puts['strike'])))
min_strike = min(strikes)
max_strike = max(strikes)

strike_range = st.sidebar.slider("Strike price range", float(min_strike), float(max_strike), (float(min_strike), float(max_strike)))
filtered_strikes = [s for s in strikes if strike_range[0] <= s <= strike_range[1]]

strategy = st.sidebar.selectbox(
    "Select strategy",
    [
        "Sell Put",
        "Sell Call",
        "Bull Call Spread",
        "Bear Put Spread",
        "Straddle",
        "Iron Condor",
        "Covered Call"
    ]
)

st.sidebar.markdown("---")

# ----------------- 选择执行价 -----------------
def select_strike(label, strikes):
    return st.sidebar.selectbox(label, strikes)

# Initialize strike selections
strike1 = None
strike2 = None
strike3 = None
strike4 = None

if strategy == "Sell Put":
    strike1 = select_strike("Put Strike Price", filtered_strikes)
elif strategy == "Sell Call":
    strike1 = select_strike("Call Strike Price", filtered_strikes)
elif strategy == "Bull Call Spread":
    strike1 = select_strike("Long Call Strike", filtered_strikes)
    strike2 = select_strike("Short Call Strike (> Long Call)", [s for s in filtered_strikes if s > strike1])
elif strategy == "Bear Put Spread":
    strike1 = select_strike("Long Put Strike", filtered_strikes)
    strike2 = select_strike("Short Put Strike (< Long Put)", [s for s in filtered_strikes if s < strike1])
elif strategy == "Straddle":
    strike1 = select_strike("Strike Price", filtered_strikes)
elif strategy == "Iron Condor":
    strike1 = select_strike("Long Put Strike", filtered_strikes)
    strike2 = select_strike("Short Put Strike (> Long Put)", [s for s in filtered_strikes if s > strike1])
    strike3 = select_strike("Short Call Strike (> Short Put)", [s for s in filtered_strikes if s > strike2])
    strike4 = select_strike("Long Call Strike (> Short Call)", [s for s in filtered_strikes if s > strike3])
elif strategy == "Covered Call":
    strike1 = select_strike("Stock Price (for reference)", filtered_strikes)
    strike2 = select_strike("Call Strike to Sell", filtered_strikes)

# ----------------- 获取期权价格 -----------------
def get_option_price(df, strike, right='call', price_type='ask'):
    if df.empty or strike is None:
        return None
    filt = df[(df['strike'] == strike)]
    if filt.empty:
        return None
    return float(filt[price_type].iloc[0])

# 现价 (用最近交易价做参考)
underlying_price = ticker.history(period="1d")['Close'][-1]

# ----------------- 策略计算 -----------------
def calc_sell_put(strike):
    ask_price = get_option_price(puts, strike, right='put', price_type='ask')
    if ask_price is None:
        return None
    cost = ask_price * 100  # 收取期权费
    max_loss = strike * 100 - cost
    max_profit = cost
    breakeven = strike - ask_price
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "cost": -cost,
        "breakeven": breakeven
    }

def calc_sell_call(strike):
    ask_price = get_option_price(calls, strike, right='call', price_type='ask')
    if ask_price is None:
        return None
    cost = ask_price * 100
    max_loss = 1e10  # 理论无限亏损
    max_profit = cost
    breakeven = strike + ask_price
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "cost": -cost,
        "breakeven": breakeven
    }

def calc_bull_call_spread(long_strike, short_strike):
    long_ask = get_option_price(calls, long_strike, 'call', 'ask')
    short_bid = get_option_price(calls, short_strike, 'call', 'bid')
    if long_ask is None or short_bid is None:
        return None
    cost = (long_ask - short_bid) * 100
    max_profit = (short_strike - long_strike) * 100 - cost
    max_loss = cost
    breakeven = long_strike + cost / 100
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "cost": -cost,
        "breakeven": breakeven
    }

def calc_bear_put_spread(long_strike, short_strike):
    long_ask = get_option_price(puts, long_strike, 'put', 'ask')
    short_bid = get_option_price(puts, short_strike, 'put', 'bid')
    if long_ask is None or short_bid is None:
        return None
    cost = (long_ask - short_bid) * 100
    max_profit = (long_strike - short_strike) * 100 - cost
    max_loss = cost
    breakeven = long_strike - cost / 100
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "cost": -cost,
        "breakeven": breakeven
    }

def calc_straddle(strike):
    call_ask = get_option_price(calls, strike, 'call', 'ask')
    put_ask = get_option_price(puts, strike, 'put', 'ask')
    if call_ask is None or put_ask is None:
        return None
    cost = (call_ask + put_ask) * 100
    max_profit = 1e10  # 理论无限
    breakeven1 = strike - cost / 100
    breakeven2 = strike + cost / 100
    return {
        "max_profit": max_profit,
        "max_loss": cost,
        "cost": -cost,
        "breakeven1": breakeven1,
        "breakeven2": breakeven2
    }

def calc_iron_condor(long_put, short_put, short_call, long_call):
    long_put_ask = get_option_price(puts, long_put, 'put', 'ask')
    short_put_bid = get_option_price(puts, short_put, 'put', 'bid')
    short_call_bid = get_option_price(calls, short_call, 'call', 'bid')
    long_call_ask = get_option_price(calls, long_call, 'call', 'ask')
    if None in [long_put_ask, short_put_bid, short_call_bid, long_call_ask]:
        return None
    cost = (long_put_ask - short_put_bid + short_call_bid - long_call_ask) * 100
    max_profit = cost
    max_loss = (short_call - short_put - (cost / 100)) * 100
    breakeven1 = short_put + cost / 100
    breakeven2 = short_call - cost / 100
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "cost": cost,
        "breakeven1": breakeven1,
        "breakeven2": breakeven2
    }

def calc_covered_call(stock_price, call_strike):
    call_bid = get_option_price(calls, call_strike, 'call', 'bid')
    if call_bid is None:
        return None
    cost = -stock_price * 100  # 持有股票的成本（负值）
    max_profit = (call_strike - stock_price) * 100 + call_bid * 100
    max_loss = stock_price * 100 - call_bid * 100
    breakeven = stock_price - call_bid
    return {
        "max_profit": max_profit,
        "max_loss": max_loss,
        "cost": cost,
        "breakeven": breakeven
    }

# ----------------- PnL 计算 -----------------
def pnl_sell_put(strike, spot_prices, net_credit):
    # 收取权利金，最大亏损strike*100 - net_credit
    return np.where(spot_prices >= strike,
                    net_credit,
                    spot_prices * 100 - strike * 100 + net_credit)

def pnl_sell_call(strike, spot_prices, net_credit):
    # 收取权利金，理论无限亏损
    return np.where(spot_prices <= strike,
                    net_credit,
                    strike * 100 - spot_prices * 100 + net_credit)

def pnl_bull_call_spread(long_strike, short_strike, spot_prices, net_cost):
    return np.where(
        spot_prices <= long_strike,
        -net_cost,
        np.where(
            spot_prices >= short_strike,
            (short_strike - long_strike) * 100 - net_cost,
            (spot_prices - long_strike) * 100 - net_cost
        )
    )

def pnl_bear_put_spread(long_strike, short_strike, spot_prices, net_cost):
    return np.where(
        spot_prices >= long_strike,
        -net_cost,
        np.where(
            spot_prices <= short_strike,
            (long_strike - short_strike) * 100 - net_cost,
            (long_strike - spot_prices) * 100 - net_cost
        )
    )

def pnl_straddle(strike, spot_prices, net_cost):
    return np.abs(spot_prices - strike) * 100 - net_cost

def pnl_iron_condor(long_put, short_put, short_call, long_call, spot_prices, net_credit):
    pnl = np.zeros_like(spot_prices)
    # Loss beyond short put strike
    idx = spot_prices < long_put
    pnl[idx] = (spot_prices[idx] - long_put) * 100 + net_credit
    # Between long_put and short_put
    idx = (spot_prices >= long_put) & (spot_prices <= short_put)
    pnl[idx] = net_credit
    # Between short_put and short_call
    idx = (spot_prices > short_put) & (spot_prices < short_call)
    pnl[idx] = net_credit
    # Between short_call and long_call
    idx = (spot_prices >= short_call) & (spot_prices <= long_call)
    pnl[idx] = net_credit
    # Beyond long_call strike
    idx = spot_prices > long_call
    pnl[idx] = (long_call - spot_prices[idx]) * 100 + net_credit
    return pnl

def pnl_covered_call(stock_price, call_strike, spot_prices, call_bid):
    # 持有股票 + 卖出看涨期权
    return (spot_prices - stock_price) * 100 + call_bid * 100

# ----------------- 主界面展示 -----------------
st.title(f"🧠 Options Strategy Simulator — {symbol}")

st.write(f"Underlying Price: ${underlying_price:.2f} | Expiration: {expiry}")

if strategy == "Sell Put":
    res = calc_sell_put(strike1)
    if res:
        spot_range = np.linspace(strike1*0.7, strike1*1.3, 200)
        pnl = pnl_sell_put(strike1, spot_range, res["cost"])
elif strategy == "Sell Call":
    res = calc_sell_call(strike1)
    if res:
        spot_range = np.linspace(strike1*0.7, strike1*1.3, 200)
        pnl = pnl_sell_call(strike1, spot_range, res["cost"])
elif strategy == "Bull Call Spread":
    res = calc_bull_call_spread(strike1, strike2)
    if res:
        spot_range = np.linspace(strike1*0.7, strike2*1.3, 200)
        pnl = pnl_bull_call_spread(strike1, strike2, spot_range, -res["cost"])
elif strategy == "Bear Put Spread":
    res = calc_bear_put_spread(strike1, strike2)
    if res:
        spot_range = np.linspace(strike2*0.7, strike1*1.3, 200)
        pnl = pnl_bear_put_spread(strike1, strike2, spot_range, -res["cost"])
elif strategy == "Straddle":
    res = calc_straddle(strike1)
    if res:
        spot_range = np.linspace(strike1*0.7, strike1*1.3, 200)
        pnl = pnl_straddle(strike1, spot_range, -res["cost"])
elif strategy == "Iron Condor":
    res = calc_iron_condor(strike1, strike2, strike3, strike4)
    if res:
        min_strike = min(strike1, strike2, strike3, strike4)
        max_strike = max(strike1, strike2, strike3, strike4)
        spot_range = np.linspace(min_strike*0.7, max_strike*1.3, 200)
        pnl = pnl_iron_condor(strike1, strike2, strike3, strike4, spot_range, res["cost"])
elif strategy == "Covered Call":
    res = calc_covered_call(strike1, strike2)
    if res:
        spot_range = np.linspace(strike1*0.7, strike2*1.5, 200)
        call_bid = get_option_price(calls, strike2, 'call', 'bid')
        pnl = pnl_covered_call(strike1, strike2, spot_range, call_bid)
else:
    st.warning("Unsupported strategy")

if res is None:
    st.error("Cannot find option prices for the selected strikes. Please choose different strikes.")
    st.stop()

# 显示策略参数
st.subheader("Strategy Details")
for k, v in res.items():
    if isinstance(v, float):
        st.write(f"**{k.replace('_',' ').capitalize()}:** {v:.2f}")
    else:
        st.write(f"**{k.replace('_',' ').capitalize()}:** {v}")

# 绘图
fig, ax = plt.subplots(figsize=(10,5))
ax.plot(spot_range, pnl, label="PnL")
ax.axhline(0, linestyle="--", color="black")
if strategy in ["Bull Call Spread", "Bear Put Spread"]:
    ax.axvline(strike1, linestyle=":", color="green", label="Long Strike")
    ax.axvline(strike2, linestyle=":", color="red", label="Short Strike")
elif strategy == "Iron Condor":
    ax.axvline(strike1, linestyle=":", color="green", label="Long Put")
    ax.axvline(strike2, linestyle=":", color="lime", label="Short Put")
    ax.axvline(strike3, linestyle=":", color="orange", label="Short Call")
    ax.axvline(strike4, linestyle=":", color="red", label="Long Call")
else:
    ax.axvline(strike1, linestyle=":", color="blue", label="Strike")

ax.set_xlabel("Underlying Price at Expiration")
ax.set_ylabel("Profit / Loss ($)")
ax.set_title(f"{strategy} PnL for {symbol}")
ax.legend()
st.pyplot(fig)
