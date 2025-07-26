import streamlit as st
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(page_title="Options Strategy Simulator", layout="wide")
st.title("🧠 Options Strategy Simulator")

# 初始化策略和持仓
if "strategies" not in st.session_state:
    st.session_state.strategies = []
if "positions" not in st.session_state:
    st.session_state.positions = []

with st.sidebar:
    st.header("Underlying & Option Chain Configuration")

    # 标的代码输入
    symbol = st.text_input("Enter stock symbol (e.g. AMD)", value="AMD").upper()

    expirations = []
    ticker = None
    if symbol:
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
        except Exception as e:
            st.error(f"Error fetching option expirations: {e}")

    expiry = None
    if expirations:
        expiry = st.selectbox("Select expiration date", expirations)
    else:
        st.info("No expirations found or enter valid symbol")

    st.markdown("---")
    st.subheader("Filter Option Strike Price Range")
    min_price = st.number_input("Min strike price", value=100.0)
    max_price = st.number_input("Max strike price", value=200.0)

    st.markdown("---")
    st.header("Strategy & Position Configuration")

    strategy_type = st.selectbox("Select strategy", [
        "Sell Put", "Sell Call", "Bull Call Spread", "Straddle", "Iron Condor", "Covered Call"
    ])

    underlying_price = st.number_input("Current underlying price ($)", value=166.47)

    strike1 = st.number_input("Strike price 1 ($)", value=160.0)
    strike2 = None
    strike3 = None
    strike4 = None

    if strategy_type in ["Bull Call Spread", "Straddle", "Covered Call"]:
        strike2 = st.number_input("Strike price 2 ($)", value=180.0)

    if strategy_type == "Iron Condor":
        strike2 = st.number_input("Strike price 2 (Short Put) ($)", value=155.0)
        strike3 = st.number_input("Strike price 3 (Short Call) ($)", value=175.0)
        strike4 = st.number_input("Strike price 4 (Long Call) ($)", value=185.0)

    option_price1 = st.number_input("Option price 1 ($)", value=2.3)
    option_price2 = st.number_input("Option price 2 ($)", value=0.8) if strike2 else 0.0
    option_price3 = st.number_input("Option price 3 ($)", value=0.5) if strike3 else 0.0
    option_price4 = st.number_input("Option price 4 ($)", value=0.3) if strike4 else 0.0

    quantity = st.number_input("Number of contracts (100 shares each)", value=1, step=1)

    if st.button("➕ Add to strategy portfolio"):
        st.session_state.strategies.append({
            "type": strategy_type,
            "underlying": underlying_price,
            "strike1": strike1,
            "strike2": strike2,
            "strike3": strike3,
            "strike4": strike4,
            "price1": option_price1,
            "price2": option_price2,
            "price3": option_price3,
            "price4": option_price4,
            "qty": quantity,
            "expiry": expiry
        })

    st.divider()
    st.subheader("Add Existing Stock Position")
    cost_basis = st.number_input("Stock cost basis ($)", value=165.0)
    shares = st.number_input("Number of shares held", value=100)
    if st.button("📥 Add position"):
        st.session_state.positions.append({"cost": cost_basis, "shares": shares})

col1, col2 = st.columns([3, 2])

# Option chain display on left
with col1:
    if expiry and ticker:
        try:
            opt_chain = ticker.option_chain(expiry)
            calls = opt_chain.calls
            puts = opt_chain.puts

            calls_filtered = calls[(calls['strike'] >= min_price) & (calls['strike'] <= max_price)]
            puts_filtered = puts[(puts['strike'] >= min_price) & (puts['strike'] <= max_price)]

            st.subheader(f"Calls for {symbol} expiring on {expiry} (Strike {min_price} - {max_price})")
            st.dataframe(calls_filtered[['contractSymbol', 'strike', 'bid', 'ask', 'lastPrice', 'volume']])

            st.subheader(f"Puts for {symbol} expiring on {expiry} (Strike {min_price} - {max_price})")
            st.dataframe(puts_filtered[['contractSymbol', 'strike', 'bid', 'ask', 'lastPrice', 'volume']])

        except Exception as e:
            st.error(f"Error fetching option chain data: {e}")
    else:
        st.info("Enter valid symbol and select expiration date to view option chain.")

# Strategy profit & details on right
with col2:
    st.subheader("📊 Strategy Profit Chart & Details")

    if st.session_state.strategies:
        spot_range = np.linspace(underlying_price * 0.7, underlying_price * 1.3, 200)
        total_pnl = np.zeros_like(spot_range)

        # 只画最后添加的策略盈亏示例
        strat = st.session_state.strategies[-1]

        # 解析执行价和价格，方便绘图
        strike1 = strat.get("strike1")
        strike2 = strat.get("strike2")
        strike3 = strat.get("strike3")
        strike4 = strat.get("strike4")
        price1 = strat.get("price1")
        price2 = strat.get("price2")
        price3 = strat.get("price3")
        price4 = strat.get("price4")
        qty = strat.get("qty")
        strategy = strat.get("type")

        mult = qty * 100
        pnl = np.zeros_like(spot_range)

        # 根据策略类型计算pnl
        if strategy == "Sell Put":
            pnl = np.where(
                spot_range < strike1,
                (spot_range - strike1) + price1,
                price1
            ) * mult

        elif strategy == "Sell Call":
            pnl = np.where(
                spot_range > strike1,
                (strike1 - spot_range) + price1,
                price1
            ) * mult

        elif strategy == "Bull Call Spread":
            pnl = np.where(
                spot_range <= strike1,
                -price1 * mult,
                np.where(
                    spot_range >= strike2,
                    (strike2 - strike1 - price1 + price2) * mult,
                    ((spot_range - strike1) - price1 + price2) * mult
                )
            )

        elif strategy == "Straddle":
            pnl = (-np.abs(spot_range - strike1) + price1 + price2) * mult

        elif strategy == "Iron Condor":
            # IC = Long Put (strike1), Short Put (strike2), Short Call (strike3), Long Call (strike4)
            put_long = np.where(
                spot_range < strike1,
                (strike1 - spot_range) - price1,
                -price1
            ) * mult
            put_short = np.where(
                (spot_range >= strike1) & (spot_range < strike2),
                price2,
                np.where(spot_range < strike1, price2 - (strike2 - spot_range), price2)
            ) * mult * -1
            call_short = np.where(
                (spot_range > strike3) & (spot_range <= strike4),
                price3,
                np.where(spot_range > strike4, price3 - (spot_range - strike4), price3)
            ) * mult * -1
            call_long = np.where(
                spot_range > strike4,
                (spot_range - strike4) - price4,
                -price4
            ) * mult

            pnl = put_long + put_short + call_short + call_long

        elif strategy == "Covered Call":
            # Covered call = stock - short call
            stock_pnl = (spot_range - underlying_price) * qty * 100
            call_short = np.where(
                spot_range > strike2,
                price2 - (spot_range - strike2),
                price2
            ) * qty * 100 * -1
            pnl = stock_pnl + call_short

        total_pnl += pnl

        # 画图并标注strike价格
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(spot_range, pnl, label=f"{strategy} PnL")

        ax.axhline(0, linestyle="--", color="black")

        def mark_strike(ax, price, color, label):
            if price is None:
                return
            ax.axvline(price, linestyle=":", color=color)
            ylim = ax.get_ylim()
            y_pos = ylim[1] * 0.95
            ax.text(price, y_pos, f"{price:.2f}", color=color, rotation=90,
                    verticalalignment='top', horizontalalignment='right',
                    fontsize=9, fontweight='bold')

        if strategy in ["Bull Call Spread", "Bear Put Spread"]:
            mark_strike(ax, strike1, "green", "Long Strike")
            mark_strike(ax, strike2, "red", "Short Strike")
        elif strategy == "Iron Condor":
            mark_strike(ax, strike1, "green", "Long Put")
            mark_strike(ax, strike2, "lime", "Short Put")
            mark_strike(ax, strike3, "orange", "Short Call")
            mark_strike(ax, strike4, "red", "Long Call")
        elif strategy == "Covered Call":
            mark_strike(ax, strike1, "blue", "Stock Price")
            mark_strike(ax, strike2, "red", "Short Call")
        else:
            mark_strike(ax, strike1, "blue", "Strike")

        ax.set_xlabel("Underlying Price at Expiration")
        ax.set_ylabel("Profit / Loss ($)")
        ax.set_title(f"{strategy} PnL for {symbol}")
        ax.legend()
        st.pyplot(fig)
        plt.clf()

        # 显示策略参数详细信息
        st.subheader("Strategy Details")
        res = {
            "strategy": strategy,
            "strike1": strike1,
            "strike2": strike2,
            "strike3": strike3,
            "strike4": strike4,
            "price1": price1,
            "price2": price2,
            "price3": price3,
            "price4": price4,
            "quantity": qty,
            "expiry": expiry,
        }
        for k, v in res.items():
            if v is not None:
                if isinstance(v, float):
                    st.write(f"**{k.replace('_',' ').capitalize()}:** {v:.2f}")
                else:
                    st.write(f"**{k.replace('_',' ').capitalize()}:** {v}")

    else:
        st.info("No strategies added yet.")

st.caption("⚠️ This tool is for educational and simulation purposes only, not investment advice.")
