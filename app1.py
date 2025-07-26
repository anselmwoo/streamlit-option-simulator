import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Options Strategy Simulator", layout="wide")

st.title("🧠 Options Strategy Simulator - AMD Example")

# Initialization
if "strategies" not in st.session_state:
    st.session_state.strategies = []
if "positions" not in st.session_state:
    st.session_state.positions = []

# -------------------- Sidebar: Strategy Selection and Position Input --------------------
with st.sidebar:
    st.header("Strategy and Position Configuration")
    strategy_type = st.selectbox("Select Strategy", ["Sell Put", "Sell Call", "Bull Call Spread", "Straddle"])

    st.subheader("Parameter Input")
    underlying_price = st.number_input("Current Underlying Price ($)", value=166.47)
    strike1 = st.number_input("Strike Price 1 ($)", value=160.0)
    strike2 = None
    if strategy_type in ["Bull Call Spread", "Straddle"]:
        strike2 = st.number_input("Strike Price 2 ($)", value=180.0)

    expiry_days = st.slider("Days to Expiration", 7, 60, 30)
    option_price1 = st.number_input("Option Price 1 ($)", value=2.3)
    option_price2 = st.number_input("Option Price 2 ($)", value=0.8) if strike2 else 0.0
    quantity = st.number_input("Number of Contracts (100 shares each)", value=1, step=1)

    submit = st.button("➕ Add to Strategy Portfolio")

    if submit:
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
    st.subheader("Existing Position Entry")
    cost_basis = st.number_input("Stock Cost Basis ($)", value=165.0)
    shares = st.number_input("Number of Shares Held", value=100)
    if st.button("📥 Add Position"):
        st.session_state.positions.append({"cost": cost_basis, "shares": shares})

# -------------------- Main Area: Strategy Display and Profit Calculation --------------------
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📊 Strategy Profit Chart")
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
        plt.plot(spot_range, stock_pnl, linestyle="--", label="Position P&L")

    plt.plot(spot_range, total_pnl, label="Total Portfolio P&L", color="black", linewidth=2)
    plt.axhline(0, color="gray", linestyle="--")
    plt.axvline(underlying_price, color="red", linestyle=":", label="Current Price")
    plt.legend()
    plt.xlabel("Underlying Price at Expiration")
    plt.ylabel("Strategy Profit/Loss ($)")
    st.pyplot(plt.gcf())
    plt.clf()

with col2:
    st.subheader("📋 Strategy Details and Scoring")
    df = pd.DataFrame(st.session_state.strategies)
    if not df.empty:
        df_display = df.copy()

        # Convert prices and strikes to numeric to avoid errors
        df_display["price1"] = pd.to_numeric(df_display["price1"], errors="coerce")
        df_display["price2"] = pd.to_numeric(df_display["price2"], errors="coerce").fillna(0.0)

        df_display["strike1"] = pd.to_numeric(df_display["strike1"], errors="coerce")
        df_display["strike2"] = pd.to_numeric(df_display["strike2"], errors="coerce").fillna(0.0)

        # Calculate cost = (price1 - price2) * 100
        df_display["Cost"] = ((df_display["price1"] - df_display["price2"]).fillna(df_display["price1"])) * 100

        # Calculate max profit
        df_display["Max Profit"] = np.where(
            df_display["type"] == "Bull Call Spread",
            (df_display["strike2"] - df_display["strike1"]) * 100 - df_display["Cost"],
            df_display["price1"] * 100
        )

        # Prevent division by zero
        df_display["Cost"] = df_display["Cost"].replace(0, np.nan)

        # Calculate return rate, fill NA with 0
        df_display["Return Rate"] = (df_display["Max Profit"] / df_display["Cost"]).round(2).fillna(0.0)

        # Calculate strategy score, simple weighted example
        df_display["Strategy Score"] = (df_display["Return Rate"] * 0.6 + df_display["Max Profit"] / 100 * 0.4).round(1)

        st.dataframe(df_display[["type", "strike1", "strike2", "Cost", "Max Profit", "Return Rate", "Strategy Score"]])
    else:
        st.info("No strategies added yet.")

st.caption("⚠️ This tool is for educational and simulation purposes only, not investment advice.")
