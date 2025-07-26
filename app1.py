import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import plotly.graph_objs as go

st.set_page_config(page_title="高级期权策略优化器", layout="wide")
st.title("📈 高级期权策略优化器")

symbol = st.text_input("请输入标的代码（如 AMD）:", "AMD").upper()
stock = yf.Ticker(symbol)
exps = stock.options

if not exps:
    st.error("无期权数据")
    st.stop()

exp = st.selectbox("选择到期日", exps)
opt_chain = stock.option_chain(exp)
calls = opt_chain.calls
puts = opt_chain.puts

price_min = st.number_input("价格区间最低", value=80.0)
price_max = st.number_input("价格区间最高", value=140.0)
step = st.number_input("价格步长", value=1.0)
invest_limit = st.number_input("最大投入金额", value=500.0)

prices = np.arange(price_min, price_max + step, step)

def bull_call_spread(calls):
    res = []
    for i in range(len(calls)):
        for j in range(i+1, len(calls)):
            buy = calls.iloc[i]
            sell = calls.iloc[j]
            debit = buy['ask'] - sell['bid']
            if debit <= 0 or debit > invest_limit:
                continue
            max_profit = sell['strike'] - buy['strike'] - debit
            breakeven = buy['strike'] + debit
            pnl = np.piecewise(
                prices,
                [prices <= buy['strike'], (prices > buy['strike']) & (prices < sell['strike']), prices >= sell['strike']],
                [lambda x: -debit, lambda x: x - buy['strike'] - debit, lambda x: max_profit]
            )
            pos_prob = np.mean(pnl > 0)
            avg_return = np.mean(pnl / debit)
            res.append({'type':'Bull Call Spread',
                        'buy_strike':buy['strike'],
                        'sell_strike':sell['strike'],
                        'cost': debit,
                        'max_profit': max_profit,
                        'breakeven': breakeven,
                        'pnl': pnl,
                        'pos_prob': pos_prob,
                        'avg_return': avg_return})
    return res


def sell_put(puts):
    res = []
    for _, put in puts.iterrows():
        credit = put['bid']
        if credit <= 0 or credit > invest_limit:
            continue
        strike = put['strike']
        max_loss = strike - credit
        pnl = np.array([credit if p >= strike else credit - (strike - p) for p in prices])
        pos_prob = np.mean(pnl > 0)
        avg_return = np.mean(pnl / credit)
        res.append({'type':'Sell Put',
                    'strike': strike,
                    'credit': credit,
                    'max_loss': max_loss,
                    'pnl': pnl,
                    'pos_prob': pos_prob,
                    'avg_return': avg_return})
    return res

def sell_call(calls):
    res = []
    for _, call in calls.iterrows():
        credit = call['bid']
        if credit <= 0 or credit > invest_limit:
            continue
        strike = call['strike']
        pnl = np.array([credit if p <= strike else credit - (p - strike) for p in prices])
        pos_prob = np.mean(pnl > 0)
        avg_return = np.mean(pnl / credit)
        res.append({'type':'Sell Call',
                    'strike': strike,
                    'credit': credit,
                    'pnl': pnl,
                    'pos_prob': pos_prob,
                    'avg_return': avg_return})
    return res

# 汇总所有策略
bull_call_res = bull_call_spread(calls)
sell_put_res = sell_put(puts)
sell_call_res = sell_call(calls)

all_strategies = bull_call_res + sell_put_res + sell_call_res

# 选择排序指标：先选平均收益和正收益概率的综合
sorted_strats = sorted(all_strategies, key=lambda x: (x['avg_return'], x['pos_prob']), reverse=True)

top_n = 5
top_strategies = sorted_strats[:top_n]

st.header(f"前 {top_n} 优策略（综合收益和概率）")

for i, strat in enumerate(top_strategies):
    st.subheader(f"{i+1}. 策略类型：{strat['type']}")
    if strat['type'] == 'Bull Call Spread':
        st.write(f"买入执行价：{strat['buy_strike']}, 卖出执行价：{strat['sell_strike']}")
        st.write(f"成本：{strat['cost']:.2f}, 最大收益：{strat['max_profit']:.2f}, 盈亏平衡点：{strat['breakeven']:.2f}")
    else:
        st.write(f"执行价：{strat['strike']}, 权利金：{strat['credit']:.2f}")
        if 'max_loss' in strat:
            st.write(f"最大亏损：{strat['max_loss']:.2f}")
    st.write(f"平均收益率：{strat['avg_return']*100:.2f}%, 正收益概率：{strat['pos_prob']*100:.2f}%")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prices, y=strat['pnl'], mode='lines', name='PnL'))
    fig.update_layout(title=f"策略收益曲线 - {strat['type']}",
                      xaxis_title="股票价格",
                      yaxis_title="收益 ($)",
                      template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
