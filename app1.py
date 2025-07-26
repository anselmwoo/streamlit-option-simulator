import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Options Strategy Simulator", layout="wide")

st.title("🧠 Options Strategy Simulator - AMD Example")

# 初始化策略和持仓
if "strategies" not in st.session_state:
    st.session_state.strategies = []
if "positions" not in st.session_state:
    st.session_state.positions = []

# ------------- 左侧：标的输入 + 期权链获取 + 策略参数 -------------
with st.sidebar:
    st.header("Underlying & Option Chain Configuration")

    # 输入标的代码
    symbol = st.text_input("Enter stock symbol (e.g. AMD)", value="AMD").upper()

    # 获取期权到期日
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

    strategy_type = st.selectbox("Select strategy", ["Sell Put", "Sell Call", "Bull Call Spread", "Straddle"])

    st.subheader("Strategy Parameters")
    underlying_price = st.number_input("Current underlying price ($)", value=166.47)
    strike1 = st.number_input("Strike price 1 ($)", value=160.0)
    strike2 = None
    if strategy_type in ["Bull Call Spread", "Straddle"]:
        strike2 = st.number_input("Strike price 2 ($)", value=180.0)

    expiry_days = st.slider("Days to expiration", 7, 60, 30)
    option_price1 = st.number_input("Option price 1 ($)", value=2.3)
    option_price2 = st.number_input("Option price 2 ($)", value=0.8) if strike2 else 0.0
    quantity = st.number_input("Number of contracts (100 shares each)", value=1, step=1)

    if st.button("➕ Add to strategy portfolio"):
        st.session_state.strategies.append({
            "type": strategy_type,
            "underlying": underlying_price,
            "strike1": strike1,
            "strike2": strike2,
            "price1": option_price1,
            "price2": option_price2,
            "qty": quantity,
            "expiry": expiry_days
        })

    st.divider()
    st.subheader("Add Existing Stock Position")
    cost_basis = st.number_input("Stock cost basis ($)", value=165.0)
    shares = st.number_input("Number of shares held", value=100)
    if st.button("📥 Add position"):
        st.session_state.positions.append({"cost": cost_basis, "shares": shares})

# ------------- 主区 -------------
col1, col2 = st.columns([3, 2])

# 期权链展示（Calls和Puts）
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

# 策略收益图及策略明细
with col2:
    st.subheader("📊 Strategy Profit Chart & Details")

    # 画策略收益图
    if st.session_state.strategies:
        spot_range = np.linspace(underlying_price * 0.7, underlying_price * 1.3, 200)
        total_pnl = np.zeros_like(spot_range)

        for strat in st.session_state.strategies:
            pnl = np.zeros_like(spot_range)
            mult = strat["qty"] * 100

            if strat["type"] == "Sell Put":
                pnl = np.where(
                    spot_range < strat["strike1"],
                    (spot_range - strat["strike1"]) + strat["price1"],
                    strat["price1"]
                ) * mult

            elif strat["type"] == "Sell Call":
                pnl = np.where(
                    spot_range > strat["strike1"],
                    (strat["strike1"] - spot_range) + strat["price1"],
                    strat["price1"]
                ) * mult

            elif strat["type"] == "Bull Call Spread":
                pnl = np.where(
                    spot_range <= strat["strike1"],
                    -strat["price1"] * mult,
                    np.where(
                        spot_range >= strat["strike2"],
                        (strat["strike2"] - strat["strike1"] - strat["price1"] + strat["price2"]) * mult,
                        ((spot_range - strat["strike1"]) - strat["price1"] + strat["price2"]) * mult
                    )
                )

            elif strat["type"] == "Straddle":
                pnl = (
                    -np.abs(spot_range - strat["strike1"]) + strat["price1"] + strat["price2"]
                ) * mult

            total_pnl += pnl
            plt.plot(spot_range, pnl, label=strat["type"])

        for pos in st.session_state.positions:
            stock_pnl = (spot_range - pos["cost"]) * pos["shares"]
            total_pnl += stock_pnl
            plt.plot(spot_range, stock_pnl, linestyle="--", label="Stock Position P&L")

        plt.plot(spot_range, total_pnl, label="Total Portfolio P&L", color="black", linewidth=2)
        plt.axhline(0, color="gray", linestyle="--")
        plt.axvline(underlying_price, color="red", linestyle=":", label="Current Price")
        plt.legend()
        plt.xlabel("Underlying Price at Expiration")
        plt.ylabel("Profit / Loss ($)")
        st.pyplot(plt.gcf())
        plt.clf()

        # 策略明细
        df = pd.DataFrame(st.session_state.strategies)
        df_display = df.copy()

        df_display["price1"] = pd.to_numeric(df_display["price1"], errors="coerce")
        df_display["price2"] = pd.to_numeric(df_display["price2"], errors="coerce").fillna(0.0)

        df_display["strike1"] = pd.to_numeric(df_display["strike1"], errors="coerce")
        df_display["strike2"] = pd.to_numeric(df_display["strike2"], errors="coerce").fillna(0.0)

        df_display["Cost"] = ((df_display["price1"] - df_display["price2"]).fillna(df_display["price1"])) * 100
        df_display["Max Profit"] = np.where(
            df_display["type"] == "Bull Call Spread",
            (df_display["strike2"] - df_display["strike1"]) * 100 - df_display["Cost"],
            df_display["price1"] * 100
        )
        df_display["Cost"] = df_display["Cost"].replace(0, np.nan)
        df_display["Return Rate"] = (df_display["Max Profit"] / df_display["Cost"]).round(2).fillna(0.0)
        df_display["Strategy Score"] = (df_display["Return Rate"] * 0.6 + df_display["Max Profit"] / 100 * 0.4).round(1)

        st.dataframe(df_display[["type", "strike1", "strike2", "Cost", "Max Profit", "Return Rate", "Strategy Score"]])

    else:
        st.info("No strategies added yet.")

st.caption("⚠️ This tool is for educational and simulation purposes only, not investment advice.")
