import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Options Strategy Simulator", layout="wide")

st.title("🧠 Options Strategy Simulator")

# 初始化
if "strategies" not in st.session_state:
    st.session_state.strategies = []
if "positions" not in st.session_state:
    st.session_state.positions = []

# --- 左侧栏：标的、到期日、价格范围、策略配置 ---
with st.sidebar:
    st.header("Underlying & Option Chain Configuration")

    # 输入标的代码
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
    st.header("Strategy Configuration")

    strategy_type = st.selectbox("Select strategy", [
        "Sell Put", "Sell Call", "Bull Call Spread", "Straddle",
        "Iron Condor", "Covered Call"
    ])

    underlying_price = 0.0
    if ticker:
        hist = ticker.history(period="1d")
        if not hist.empty:
            underlying_price = hist["Close"].iloc[-1]

    st.write(f"Current underlying price: ${underlying_price:.2f}")

    # 输入执行价，依据策略类型
    strike1 = st.number_input("Strike price 1 ($)", value=underlying_price*0.95 if underlying_price > 0 else 100.0)
    strike2 = strike3 = strike4 = None
    if strategy_type in ["Bull Call Spread", "Iron Condor", "Covered Call"]:
        strike2 = st.number_input("Strike price 2 ($)", value=underlying_price*1.05 if underlying_price > 0 else 110.0)
    if strategy_type == "Iron Condor":
        strike3 = st.number_input("Strike price 3 ($)", value=underlying_price*1.10 if underlying_price > 0 else 115.0)
        strike4 = st.number_input("Strike price 4 ($)", value=underlying_price*1.15 if underlying_price > 0 else 120.0)

    quantity = st.number_input("Number of contracts (100 shares each)", value=1, step=1)

    st.markdown("---")

    # 读取期权链数据（calls/puts）
    calls, puts = None, None
    if ticker and expiry:
        try:
            opt_chain = ticker.option_chain(expiry)
            calls = opt_chain.calls
            puts = opt_chain.puts
            # 过滤执行价范围
            calls = calls[(calls['strike'] >= min_price) & (calls['strike'] <= max_price)]
            puts = puts[(puts['strike'] >= min_price) & (puts['strike'] <= max_price)]
        except Exception as e:
            st.error(f"Error fetching option chain data: {e}")

    # 取价格函数：买入取ask，卖出取bid
    def get_option_price(option_type, strike, is_buy=True):
        df = calls if option_type == 'call' else puts
        if df is None:
            return 0.0
        row = df[df['strike'] == strike]
        if row.empty:
            return 0.0
        price = row['ask'].values[0] if is_buy else row['bid'].values[0]
        return price if not pd.isna(price) else 0.0

    # 点击按钮添加策略
    if st.button("➕ Add to strategy portfolio"):
        price1 = price2 = price3 = price4 = 0.0

        if strategy_type == "Sell Put":
            price1 = get_option_price('put', strike1, is_buy=False)
        elif strategy_type == "Sell Call":
            price1 = get_option_price('call', strike1, is_buy=False)
        elif strategy_type == "Bull Call Spread":
            price1 = get_option_price('call', strike1, is_buy=True)
            price2 = get_option_price('call', strike2, is_buy=False)
        elif strategy_type == "Straddle":
            price1 = get_option_price('call', strike1, is_buy=True)
            price2 = get_option_price('put', strike1, is_buy=True)
        elif strategy_type == "Iron Condor":
            price1 = get_option_price('put', strike1, is_buy=True)
            price2 = get_option_price('put', strike2, is_buy=False)
            price3 = get_option_price('call', strike3, is_buy=False)
            price4 = get_option_price('call', strike4, is_buy=True)
        elif strategy_type == "Covered Call":
            # Covered Call: Long stock + Sell call
            price1 = 0.0  # No option price for stock
            price2 = get_option_price('call', strike2, is_buy=False)

        st.session_state.strategies.append({
            "type": strategy_type,
            "underlying": underlying_price,
            "strike1": strike1,
            "strike2": strike2,
            "strike3": strike3,
            "strike4": strike4,
            "price1": price1,
            "price2": price2,
            "price3": price3,
            "price4": price4,
            "qty": quantity,
            "expiry": expiry
        })

    st.divider()
    st.subheader("Add Existing Stock Position")
    cost_basis = st.number_input("Stock cost basis ($)", value=underlying_price)
    shares = st.number_input("Number of shares held", value=0)
    if st.button("📥 Add position"):
        if shares > 0:
            st.session_state.positions.append({"cost": cost_basis, "shares": shares})

# --- 主区 ---
col1, col2 = st.columns([3, 2])

with col1:
    if calls is not None and puts is not None:
        st.subheader(f"{symbol} Calls (Strike {min_price} - {max_price}) expiring {expiry}")
        st.dataframe(calls[['contractSymbol', 'strike', 'bid', 'ask', 'lastPrice', 'volume']])

        st.subheader(f"{symbol} Puts (Strike {min_price} - {max_price}) expiring {expiry}")
        st.dataframe(puts[['contractSymbol', 'strike', 'bid', 'ask', 'lastPrice', 'volume']])
    else:
        st.info("Enter valid symbol and select expiration date to view option chain.")

with col2:
    st.subheader("📊 Strategy Profit Chart & Details")

    if st.session_state.strategies:
        spot_range = np.linspace(underlying_price * 0.7, underlying_price * 1.3, 300)
        total_pnl = np.zeros_like(spot_range)

        plt.figure(figsize=(8,5))
        for strat in st.session_state.strategies:
            pnl = np.zeros_like(spot_range)
            mult = strat["qty"] * 100

            # 计算每种策略收益（根据策略类型）
            if strat["type"] == "Sell Put":
                # Short put payoff
                pnl = np.where(
                    spot_range < strat["strike1"],
                    (spot_range - strat["strike1"]) + strat["price1"],
                    strat["price1"]
                ) * mult

                profit_range = (strat["strike1"], np.inf)

            elif strat["type"] == "Sell Call":
                pnl = np.where(
                    spot_range > strat["strike1"],
                    (strat["strike1"] - spot_range) + strat["price1"],
                    strat["price1"]
                ) * mult
                profit_range = (-np.inf, strat["strike1"])

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
                profit_range = (strat["strike1"], strat["strike2"])

            elif strat["type"] == "Straddle":
                pnl = (
                    -np.abs(spot_range - strat["strike1"]) + strat["price1"] + strat["price2"]
                ) * mult
                profit_range = None

            elif strat["type"] == "Iron Condor":
                # Iron condor = Long put1, short put2, short call3, long call4
                put_long = np.where(
                    spot_range < strat["strike1"],
                    (spot_range - strat["strike1"]) + strat["price1"],
                    strat["price1"]
                ) * mult

                put_short = np.where(
                    spot_range < strat["strike2"],
                    (strat["strike2"] - spot_range) + strat["price2"],
                    strat["price2"]
                ) * mult

                call_short = np.where(
                    spot_range > strat["strike3"],
                    (strat["strike3"] - spot_range) + strat["price3"],
                    strat["price3"]
                ) * mult

                call_long = np.where(
                    spot_range > strat["strike4"],
                    (spot_range - strat["strike4"]) + strat["price4"],
                    strat["price4"]
                ) * mult

                pnl = put_long + put_short + call_short + call_long
                profit_range = (strat["strike2"], strat["strike3"])

            elif strat["type"] == "Covered Call":
                # Covered call = long stock + short call
                stock_pnl = (spot_range - strat["underlying"]) * strat["qty"] * 100
                call_short = np.where(
                    spot_range > strat["strike2"],
                    (strat["strike2"] - spot_range) + strat["price2"],
                    strat["price2"]
                ) * strat["qty"] * 100
                pnl = stock_pnl + call_short
                profit_range = (-np.inf, strat["strike2"])

            total_pnl += pnl
            plt.plot(spot_range, pnl, label=f"{strat['type']} @ strikes {strat['strike1']}, {strat.get('strike2', '')}")

        # 显示已有股票持仓盈亏
        for pos in st.session_state.positions:
            stock_pnl = (spot_range - pos["cost"]) * pos["shares"]
            total_pnl += stock_pnl
            plt.plot(spot_range, stock_pnl, linestyle="--", label="Stock Position P&L")

        plt.plot(spot_range, total_pnl, label="Total Portfolio P&L", color="black", linewidth=2)
        plt.axhline(0, color="gray", linestyle="--")
        plt.axvline(underlying_price, color="red", linestyle=":", label="Current Price")
        plt.xlabel("Underlying Price at Expiration")
        plt.ylabel("Profit / Loss ($)")
        plt.title("Strategy Payoff at Expiration")
        plt.legend()
        st.pyplot(plt.gcf())
        plt.clf()

        # 策略明细表（含期权价格、预期收益、收益概率、盈利区间）
        details = []
        for strat in st.session_state.strategies:
            qty = strat["qty"] * 100
            prices = [strat.get(f"price{i}", 0.0) for i in range(1,5)]
            strikes = [strat.get(f"strike{i}", None) for i in range(1,5)]

            # 计算成本 = 卖出价格减买入价格乘合约数量*100（假设买入期权取正，卖出期权取负）
            # 预期收益及盈利区间简单估计
            cost = 0.0
            expected_profit = 0.0
            profit_range = ""

            if strat["type"] == "Sell Put":
                cost = prices[0] * qty
                expected_profit = cost  # 收到权利金，亏损最大strike1-标的价*qty
                profit_range = f"Price ≥ {strikes[0]:.2f}"

            elif strat["type"] == "Sell Call":
                cost = prices[0] * qty
                expected_profit = cost
                profit_range = f"Price ≤ {strikes[0]:.2f}"

            elif strat["type"] == "Bull Call Spread":
                cost = (prices[0] - prices[1]) * qty
                max_profit = (strikes[1] - strikes[0]) * qty - cost
                expected_profit = max_profit  # 简单近似
                profit_range = f"{strikes[0]:.2f} ≤ Price ≤ {strikes[1]:.2f}"

            elif strat["type"] == "Straddle":
                cost = (prices[0] + prices[1]) * qty
                expected_profit = None
                profit_range = "Volatility plays a big role"

            elif strat["type"] == "Iron Condor":
                cost = (prices[0] - prices[1] - prices[2] + prices[3]) * qty
                expected_profit = None
                profit_range = f"{strikes[1]:.2f} ≤ Price ≤ {strikes[2]:.2f}"

            elif strat["type"] == "Covered Call":
                cost = - prices[1] * qty  # 收取卖call权利金
                expected_profit = None
                profit_range = f"Price ≤ {strikes[1]:.2f}"

            details.append({
                "Strategy": strat["type"],
                "Strike Prices": ', '.join([f"{s:.2f}" for s in strikes if s]),
                "Option Prices (bid/ask used)": ', '.join([f"{p:.2f}" for p in prices if p > 0]),
                "Qty (Contracts)": strat["qty"],
                "Cost ($)": round(cost, 2),
                "Expected Profit ($)": round(expected_profit, 2) if expected_profit is not None else "N/A",
                "Profit Range": profit_range
            })

        st.dataframe(pd.DataFrame(details))

    else:
        st.info("No strategies added yet.")

st.caption("⚠️ This tool is for educational and simulation purposes only, not investment advice.")
