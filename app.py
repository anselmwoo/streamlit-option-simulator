import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go

st.set_page_config(layout="wide")

st.title("📈 AMD 期权策略模拟器（收益率优化）")

# ---------- 用户输入参数 ----------
ticker_symbol = "AMD"
ticker = yf.Ticker(ticker_symbol)

dates = ticker.options
selected_exp = st.selectbox("选择期权到期日：", dates)

min_price = st.number_input("模拟价格区间（最低）", value=90)
max_price = st.number_input("模拟价格区间（最高）", value=140)
step = st.number_input("价格间隔", value=2)
invest_limit = st.number_input("最大投入金额 ($)：", value=500)

if min_price >= max_price:
    st.error("最低价格不能高于或等于最高价格")
    st.stop()

# ---------- 拉取期权链数据 ----------
@st.cache_data
def load_option_chain(symbol, exp_date):
    opt = yf.Ticker(symbol).option_chain(exp_date)
    return opt.calls, opt.puts

calls, puts = load_option_chain(ticker_symbol, selected_exp)

# ---------- 构建策略：牛市价差（Buy Call + Sell Call） ----------
def simulate_bull_call_spreads(calls, price_range):
    results = []
    for i in range(len(calls)):
        for j in range(i + 1, len(calls)):
            buy = calls.iloc[i]
            sell = calls.iloc[j]

            debit = buy["ask"] - sell["bid"]
            if np.isnan(debit) or debit <= 0 or debit > invest_limit:
                continue

            max_profit = sell["strike"] - buy["strike"] - debit
            breakeven = buy["strike"] + debit

            pnl = []
            for price in price_range:
                if price <= buy["strike"]:
                    profit = -debit
                elif price >= sell["strike"]:
                    profit = max_profit
                else:
                    profit = price - buy["strike"] - debit
                pnl.append(profit)

            avg_return = np.mean([p / debit for p in pnl if debit != 0])
            results.append({
                "Buy Strike": buy["strike"],
                "Sell Strike": sell["strike"],
                "Cost": debit,
                "Max Profit": max_profit,
                "Breakeven": breakeven,
                "Avg Return": avg_return,
                "PnL": pnl
            })
    return sorted(results, key=lambda x: -x["Avg Return"])

# ---------- 执行模拟 ----------
if st.button("▶️ 开始模拟"):
    prices = np.arange(min_price, max_price + step, step)
    strategies = simulate_bull_call_spreads(calls, prices)

    if not strategies:
        st.warning("未找到合适的牛市价差策略组合。")
        st.stop()

    best = strategies[0]
    st.subheader("🔥 最佳牛市价差策略")
    st.markdown(f"**买入执行价：** ${best['Buy Strike']} Call")
    st.markdown(f"**卖出执行价：** ${best['Sell Strike']} Call")
    st.markdown(f"**成本：** ${best['Cost']:.2f}，最大收益：${best['Max Profit']:.2f}，盈亏平衡点：${best['Breakeven']:.2f}")
    st.markdown(f"**平均收益率：** {best['Avg Return']*100:.2f}%")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prices, y=best["PnL"], mode='lines+markers', name='策略PnL'))
    fig.update_layout(title="策略盈亏图（模拟价格 vs 收益）",
                      xaxis_title="股票价格",
                      yaxis_title="收益 ($)",
                      template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    # 可选展示前几个组合
    st.subheader("📋 收益率前5的策略：")
    top5 = pd.DataFrame(strategies[:5])
    st.dataframe(top5[["Buy Strike", "Sell Strike", "Cost", "Max Profit", "Breakeven", "Avg Return"]].round(2))
