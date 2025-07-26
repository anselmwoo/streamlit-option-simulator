import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from itertools import combinations

st.set_page_config(page_title="Options Strategy Auto-Explorer", layout="wide")
st.title("🧠 Options Strategy Auto Explorer")

# -- 左侧栏参数 --
with st.sidebar:
    symbol = st.text_input("Enter stock symbol (e.g. AMD)", value="AMD").upper()

    expirations = []
    ticker = None
    if symbol:
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
        except Exception as e:
            st.error(f"Error fetching option expirations: {e}")

    expiry = st.selectbox("Select expiration date", expirations) if expirations else None

    min_price = st.number_input("Min strike price", value=100.0)
    max_price = st.number_input("Max strike price", value=200.0)

    strategy_type = st.selectbox("Select strategy", [
        "Sell Put", "Sell Call", "Bull Call Spread", "Straddle",
        "Iron Condor", "Covered Call"
    ])

# -- 主区 --
col1, col2 = st.columns([3, 2])

calls, puts = None, None
underlying_price = 0.0
if ticker and expiry:
    try:
        opt_chain = ticker.option_chain(expiry)
        calls = opt_chain.calls
        puts = opt_chain.puts
        calls = calls[(calls['strike'] >= min_price) & (calls['strike'] <= max_price)]
        puts = puts[(puts['strike'] >= min_price) & (puts['strike'] <= max_price)]
        hist = ticker.history(period="1d")
        if not hist.empty:
            underlying_price = hist["Close"].iloc[-1]
    except Exception as e:
        st.error(f"Error fetching option chain data: {e}")

def get_price(df, strike, is_call=True, is_buy=True):
    if df is None:
        return 0.0
    row = df[(df['strike'] == strike)]
    if row.empty:
        return 0.0
    price = row['ask'].values[0] if is_buy else row['bid'].values[0]
    return price if not pd.isna(price) else 0.0

def simulate_strategy(strat_type, strikes, prices, qty, underlying):
    mult = qty * 100
    spot_range = np.linspace(underlying * 0.7, underlying * 1.3, 300)
    pnl = np.zeros_like(spot_range)

    if strat_type == "Sell Put":
        strike = strikes[0]
        price = prices[0]
        pnl = np.where(
            spot_range < strike,
            (spot_range - strike) + price,
            price
        ) * mult
        cost = price * mult
        expected_profit = cost
        profit_range = f"Price ≥ {strike:.2f}"

    elif strat_type == "Sell Call":
        strike = strikes[0]
        price = prices[0]
        pnl = np.where(
            spot_range > strike,
            (strike - spot_range) + price,
            price
        ) * mult
        cost = price * mult
        expected_profit = cost
        profit_range = f"Price ≤ {strike:.2f}"

    elif strat_type == "Bull Call Spread":
        strike1, strike2 = strikes
        price_buy, price_sell = prices
        pnl = np.where(
            spot_range <= strike1,
            -price_buy * mult,
            np.where(
                spot_range >= strike2,
                (strike2 - strike1 - price_buy + price_sell) * mult,
                ((spot_range - strike1) - price_buy + price_sell) * mult
            )
        )
        cost = (price_buy - price_sell) * mult
        max_profit = (strike2 - strike1) * mult - cost
        expected_profit = max_profit
        profit_range = f"{strike1:.2f} ≤ Price ≤ {strike2:.2f}"

    elif strat_type == "Straddle":
        strike = strikes[0]
        price_call, price_put = prices
        pnl = (-np.abs(spot_range - strike) + price_call + price_put) * mult
        cost = (price_call + price_put) * mult
        expected_profit = None
        profit_range = "Volatility sensitive"

    elif strat_type == "Iron Condor":
        strike1, strike2, strike3, strike4 = strikes
        p1, p2, p3, p4 = prices
        put_long = np.where(
            spot_range < strike1,
            (spot_range - strike1) + p1,
            p1
        ) * mult
        put_short = np.where(
            spot_range < strike2,
            (strike2 - spot_range) + p2,
            p2
        ) * mult
        call_short = np.where(
            spot_range > strike3,
            (strike3 - spot_range) + p3,
            p3
        ) * mult
        call_long = np.where(
            spot_range > strike4,
            (spot_range - strike4) + p4,
            p4
        ) * mult
        pnl = put_long + put_short + call_short + call_long
        cost = (p1 - p2 - p3 + p4) * mult
        expected_profit = None
        profit_range = f"{strike2:.2f} ≤ Price ≤ {strike3:.2f}"

    elif strat_type == "Covered Call":
        strike_call = strikes[1]
        price_call = prices[1]
        stock_pnl = (spot_range - underlying) * mult
        call_short = np.where(
            spot_range > strike_call,
            (strike_call - spot_range) + price_call,
            price_call
        ) * mult
        pnl = stock_pnl + call_short
        cost = - price_call * mult
        expected_profit = None
        profit_range = f"Price ≤ {strike_call:.2f}"

    else:
        return None

    return {
        "pnl": pnl,
        "cost": cost,
        "expected_profit": expected_profit,
        "profit_range": profit_range
    }

# 自动生成策略
strategies = []
if calls is not None and puts is not None:
    qty = 1  # 固定1合约，可改为界面输入
    if strategy_type == "Sell Put":
        # 遍历puts单腿卖出
        for strike in puts['strike']:
            price = get_price(puts, strike, is_call=False, is_buy=False)
            if price <= 0: continue
            sim = simulate_strategy(strategy_type, [strike], [price], qty, underlying_price)
            strategies.append({
                "type": strategy_type,
                "strikes": [strike],
                "prices": [price],
                "qty": qty,
                **sim
            })
    elif strategy_type == "Sell Call":
        for strike in calls['strike']:
            price = get_price(calls, strike, is_call=True, is_buy=False)
            if price <= 0: continue
            sim = simulate_strategy(strategy_type, [strike], [price], qty, underlying_price)
            strategies.append({
                "type": strategy_type,
                "strikes": [strike],
                "prices": [price],
                "qty": qty,
                **sim
            })
    elif strategy_type == "Bull Call Spread":
        # 遍历所有calls两两组合，买低卖高
        for buy_strike, sell_strike in combinations(sorted(calls['strike']), 2):
            buy_price = get_price(calls, buy_strike, is_call=True, is_buy=True)
            sell_price = get_price(calls, sell_strike, is_call=True, is_buy=False)
            if buy_price <= 0 or sell_price <= 0: continue
            sim = simulate_strategy(strategy_type, [buy_strike, sell_strike], [buy_price, sell_price], qty, underlying_price)
            strategies.append({
                "type": strategy_type,
                "strikes": [buy_strike, sell_strike],
                "prices": [buy_price, sell_price],
                "qty": qty,
                **sim
            })
    elif strategy_type == "Straddle":
        # 遍历calls和puts相同strike组合买入
        common_strikes = set(calls['strike']).intersection(set(puts['strike']))
        for strike in common_strikes:
            call_price = get_price(calls, strike, is_call=True, is_buy=True)
            put_price = get_price(puts, strike, is_call=False, is_buy=True)
            if call_price <= 0 or put_price <= 0: continue
            sim = simulate_strategy(strategy_type, [strike], [call_price, put_price], qty, underlying_price)
            strategies.append({
                "type": strategy_type,
                "strikes": [strike],
                "prices": [call_price, put_price],
                "qty": qty,
                **sim
            })
    elif strategy_type == "Iron Condor":
        # 遍历puts两档、calls两档组合（strike顺序：put_long < put_short < call_short < call_long）
        put_strikes = sorted(puts['strike'])
        call_strikes = sorted(calls['strike'])
        for put_long, put_short in combinations(put_strikes, 2):
            if put_long >= put_short:
                continue
            for call_short, call_long in combinations(call_strikes, 2):
                if call_short >= call_long:
                    continue
                # 要求 put_short < call_short 保证合理结构
                if put_short >= call_short:
                    continue
                p1 = get_price(puts, put_long, is_call=False, is_buy=True)
                p2 = get_price(puts, put_short, is_call=False, is_buy=False)
                p3 = get_price(calls, call_short, is_call=True, is_buy=False)
                p4 = get_price(calls, call_long, is_call=True, is_buy=True)
                if 0 in [p1, p2, p3, p4]:
                    continue
                sim = simulate_strategy(strategy_type,
                                        [put_long, put_short, call_short, call_long],
                                        [p1, p2, p3, p4],
                                        qty, underlying_price)
                strategies.append({
                    "type": strategy_type,
                    "strikes": [put_long, put_short, call_short, call_long],
                    "prices": [p1, p2, p3, p4],
                    "qty": qty,
                    **sim
                })
    elif strategy_type == "Covered Call":
        # 遍历call卖出执行价
        for strike in calls['strike']:
            price_call = get_price(calls, strike, is_call=True, is_buy=False)
            if price_call <= 0:
                continue
            sim = simulate_strategy(strategy_type,
                                    [underlying_price, strike],
                                    [0.0, price_call],
                                    qty, underlying_price)
            strategies.append({
                "type": strategy_type,
                "strikes": [underlying_price, strike],
                "prices": [0.0, price_call],
                "qty": qty,
                **sim
            })

# 选出预期收益最高前10策略
sorted_strats = sorted([s for s in strategies if s['expected_profit'] is not None], key=lambda x: x['expected_profit'], reverse=True)
top_strats = sorted_strats[:10]

with col1:
    st.subheader(f"Top 10 {strategy_type} Strategies by Expected Profit")
    if top_strats:
        rows = []
        for s in top_strats:
            rows.append({
                "Strategy": s["type"],
                "Strike Prices": ', '.join([f"{strike:.2f}" for strike in s["strikes"]]),
                "Option Prices (used bid/ask)": ', '.join([f"{price:.2f}" for price in s["prices"]]),
                "Qty (Contracts)": s["qty"],
                "Cost ($)": round(s["cost"], 2),
                "Expected Profit ($)": round(s["expected_profit"], 2),
                "Profit Range": s["profit_range"]
            })
        df = pd.DataFrame(rows)
        st.dataframe(df)
    else:
        st.info("No valid strategies found.")

with col2:
    st.subheader("Profit Curves of Top Strategies")
    plt.figure(figsize=(8,6))
    spot_range = np.linspace(underlying_price * 0.7, underlying_price * 1.3, 300)
    for s in top_strats:
        plt.plot(spot_range, s["pnl"], label=f"{s['type']} @ {', '.join([f'{st:.2f}' for st in s['strikes']])}")
    plt.axhline(0, color='gray', linestyle='--')
    plt.axvline(underlying_price, color='red', linestyle=':', label='Underlying Price')
    plt.xlabel("Underlying Price at Expiration")
    plt.ylabel("Profit / Loss ($)")
    plt.title(f"Profit Curves for Top {len(top_strats)} {strategy_type} Strategies")
    plt.legend()
    st.pyplot(plt.gcf())
    plt.clf()
