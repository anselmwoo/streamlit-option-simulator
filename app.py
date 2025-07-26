import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go

st.set_page_config(page_title="期权策略模拟器", layout="wide")

st.title("📈 期权策略模拟器（收益率优化）")

# 用户输入标的代码
symbol = st.text_input("请输入标的股票代码（如 AMD、AAPL、TSLA）:", value="AMD").upper()

# 拉取期权链数据函数
def get_option_chain(ticker):
    stock = yf.Ticker(ticker)
    try:
        exps = stock.options
        if not exps:
            st.warning("未找到期权到期日")
            return None, None, None
        opt_date = st.selectbox("选择期权到期日:", exps)
        opt_chain = stock.option_chain(opt_date)
        return opt_chain.calls, opt_chain.puts, opt_date
    except Exception as e:
        st.error(f"获取期权链失败: {e}")
        return None, None, None

calls, puts, selected_exp = get_option_chain(symbol)

if calls is None or puts is None:
    st.stop()

# 显示 Calls 和 Puts 期权链
st.subheader(f"📋 {symbol} Calls 期权链（到期日：{selected_exp}）")
st.dataframe(calls[['strike', 'bid', 'ask', 'impliedVolatility']].rename(columns={
    'strike': '执行价', 'bid': '买价', 'ask': '卖价', 'impliedVolatility': '隐含波动率'
}))

st.subheader(f"📋 {symbol} Puts 期权链（到期日：{selected_exp}）")
st.dataframe(puts[['strike', 'bid', 'ask', 'impliedVolatility']].rename(columns={
    'strike': '执行价', 'bid': '买价', 'ask': '卖价', 'impliedVolatility': '隐含波动率'
}))

# 模拟参数输入
st.sidebar.header("模拟参数设置")
min_price = st.sidebar.number_input("模拟价格区间（最低）", value=90.0, step=0.5)
max_price = st.sidebar.number_input("模拟价格区间（最高）", value=140.0, step=0.5)
step = st.sidebar.number_input("价格间隔", value=2.0, step=0.5)
invest_limit = st.sidebar.number_input("最大投入金额 ($)：", value=500.0, step=10.0)

if min_price >= max_price:
    st.sidebar.error("最低价格不能高于或等于最高价格")
    st.stop()

# 牛市价差策略模拟函数
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

# 执行模拟按钮
if st.button("▶️ 开始模拟牛市价差策略"):
    prices = np.arange(min_price, max_price + step, step)
    strategies = simulate_bull_call_spreads(calls, prices)

    if not strategies:
        st.warning("未找到合适的牛市价差策略组合。")
        st.stop()

    best = strategies[0]
    st.subheader("🔥 最佳牛市价差策略")
    st.markdown(f"**标的：** {symbol}")
    st.markdown(f"**到期日：** {selected_exp}")
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

    # 展示收益率前5的策略
    st.subheader("📋 收益率前5的策略：")
    top5 = pd.DataFrame(strategies[:5])
    st.dataframe(top5[["Buy Strike", "Sell Strike", "Cost", "Max Profit", "Breakeven", "Avg Return"]].round(2))
