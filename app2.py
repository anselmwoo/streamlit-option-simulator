import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# Fix for Chinese font rendering
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# Step 1: User enters stock symbol
st.sidebar.header("Select Ticker and Parameters")
ticker = st.sidebar.text_input("Enter Stock Ticker", value="AMD").upper()

try:
    stock = yf.Ticker(ticker)
    expirations = stock.options
except:
    st.error("Failed to fetch options data for this ticker.")
    st.stop()

# Step 2: User selects expiration date
expiry = st.sidebar.selectbox("Select Expiration Date", expirations)

# Step 3: Get option chain
opt_chain = stock.option_chain(expiry)
calls = opt_chain.calls.copy()
puts = opt_chain.puts.copy()

# Step 4: User selects strike price range
min_strike = int(calls["strike"].min())
max_strike = int(calls["strike"].max())
price_range = st.sidebar.slider("Select Strike Price Range", min_strike, max_strike, (min_strike + 5, max_strike - 5))

# Filter options within range
calls = calls[(calls["strike"] >= price_range[0]) & (calls["strike"] <= price_range[1])]
puts = puts[(puts["strike"] >= price_range[0]) & (puts["strike"] <= price_range[1])]

# Step 5: Display option chains
st.subheader(f"{ticker} - Call Options ({expiry})")
st.dataframe(calls[["strike", "bid", "ask", "lastPrice", "impliedVolatility"]].rename(columns={
    "strike": "Strike", "bid": "Bid", "ask": "Ask", "lastPrice": "Last", "impliedVolatility": "IV"
}))

st.subheader(f"{ticker} - Put Options ({expiry})")
st.dataframe(puts[["strike", "bid", "ask", "lastPrice", "impliedVolatility"]].rename(columns={
    "strike": "Strike", "bid": "Bid", "ask": "Ask", "lastPrice": "Last", "impliedVolatility": "IV"
}))

# Step 6: Strategy simulation - Bull Call Spread example
st.subheader("Strategy Simulation (Example: Bull Call Spread)")

underlying_price = stock.history(period="1d")["Close"].iloc[-1]

results = []

for i in range(len(calls)):
    for j in range(i + 1, len(calls)):
        buy = calls.iloc[i]
        sell = calls.iloc[j]

        strike_buy = buy["strike"]
        strike_sell = sell["strike"]

        cost = round((buy["ask"] - sell["bid"]) * 100, 2)
        max_profit = round((strike_sell - strike_buy) * 100 - cost, 2)
        breakeven = strike_buy + (cost / 100)

        # Estimate probability of profit
        prob_profit = max(0, 1 - (breakeven - underlying_price) / (underlying_price * 0.2))
        prob_profit = min(prob_profit, 1)

        roi = round(max_profit / cost, 2) if cost > 0 else 0

        results.append({
            "Strategy": f"Bull Call {strike_buy}/{strike_sell}",
            "Buy Strike": strike_buy,
            "Sell Strike": strike_sell,
            "Cost": cost,
            "Max Profit": max_profit,
            "Breakeven": round(breakeven, 2),
            "Return": roi,
            "Profit Probability (%)": round(prob_profit * 100, 1)
        })

df_results = pd.DataFrame(results)

# Step 7: Show strategy table
selected_row = st.data_editor(
    df_results,
    column_config={
        "Strategy": st.column_config.TextColumn("Strategy Name"),
        "Cost": st.column_config.NumberColumn("Cost ($)"),
        "Max Profit": st.column_config.NumberColumn("Max Profit ($)"),
        "Return": st.column_config.NumberColumn("Return / Cost", format="%.2f"),
        "Profit Probability (%)": st.column_config.NumberColumn("Win Probability (%)")
    },
    use_container_width=True,
    num_rows="dynamic",
    key="strategy_table"
)

# Step 8: Plot payoff chart (if selected)
if selected_row and isinstance(selected_row, list) and len(selected_row) > 0:
    selected = selected_row[0]  # Take the first selected row

    x = np.linspace(underlying_price * 0.8, underlying_price * 1.2, 100)
    strike1 = selected["Buy Strike"]
    strike2 = selected["Sell Strike"]
    cost = selected["Cost"]

    y = np.piecewise(x,
                     [x <= strike1, (x > strike1) & (x < strike2), x >= strike2],
                     [-cost, lambda x: (x - strike1) * 100 - cost, (strike2 - strike1) * 100 - cost])

    fig, ax = plt.subplots()
    ax.plot(x, y, label=selected["Strategy"])
    ax.axhline(0, color='gray', linestyle='--')
    ax.axvline(strike1, color='blue', linestyle='--', label='Buy Strike')
    ax.axvline(strike2, color='orange', linestyle='--', label='Sell Strike')
    ax.set_xlabel("Underlying Price")
    ax.set_ylabel("Profit ($)")
    ax.set_title(f"Payoff Chart - {selected['Strategy']}")
    ax.legend()
    st.pyplot(fig)
