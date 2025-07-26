import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 常用中文字体（Windows、macOS、Linux 环境字体可能不同）
# Windows 示例（微软雅黑）
zh_font = {'family': 'Microsoft YaHei'}

# macOS 示例（华文黑体）
# zh_font = {'family': 'STHeiti'}

# Linux 示例（需自行安装字体，比如文泉驿微米黑）
# zh_font = {'family': 'WenQuanYi Micro Hei'}

matplotlib.rcParams['font.family'] = zh_font['family']

# 防止负号显示异常
matplotlib.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="期权策略模拟器", layout="wide")

st.title("🧠 期权策略模拟器 - AMD 示例")

# 初始化
if "strategies" not in st.session_state:
    st.session_state.strategies = []
if "positions" not in st.session_state:
    st.session_state.positions = []

# -------------------- 左侧：策略选择与持仓录入 --------------------
with st.sidebar:
    st.header("策略与持仓配置")
    strategy_type = st.selectbox("选择策略", ["Sell Put", "Sell Call", "Bull Call Spread", "Straddle"])

    st.subheader("参数输入")
    underlying_price = st.number_input("当前标的价格 ($)", value=166.47)
    strike1 = st.number_input("执行价 1 ($)", value=160.0)
    strike2 = None
    if strategy_type in ["Bull Call Spread", "Straddle"]:
        strike2 = st.number_input("执行价 2 ($)", value=180.0)

    expiry_days = st.slider("到期天数", 7, 60, 30)
    option_price1 = st.number_input("期权价格 1 ($)", value=2.3)
    option_price2 = st.number_input("期权价格 2 ($)", value=0.8) if strike2 else 0.0
    quantity = st.number_input("张数 (每张=100股)", value=1, step=1)

    submit = st.button("➕ 添加到策略组合")

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
    st.subheader("已有持仓录入")
    cost_basis = st.number_input("股票持仓成本 ($)", value=165.0)
    shares = st.number_input("持仓股数", value=100)
    if st.button("📥 添加持仓"):
        st.session_state.positions.append({"cost": cost_basis, "shares": shares})

# -------------------- 中央区域：策略展示与收益计算 --------------------
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📊 策略收益图")
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
        plt.plot(spot_range, stock_pnl, linestyle="--", label="持仓盈亏")

    plt.plot(spot_range, total_pnl, label="组合总盈亏", color="black", linewidth=2)
    plt.axhline(0, color="gray", linestyle="--")
    plt.axvline(underlying_price, color="red", linestyle=":", label="当前价格")
    plt.legend()
    plt.xlabel("到期时标的价格")
    plt.ylabel("策略盈亏 ($)")
    st.pyplot(plt.gcf())
    plt.clf()

with col2:
    st.subheader("📋 策略明细与打分")
    df = pd.DataFrame(st.session_state.strategies)
    if not df.empty:
        df_display = df.copy()

        # 转换价格与执行价为数值，防止非数字出错
        df_display["price1"] = pd.to_numeric(df_display["price1"], errors="coerce")
        df_display["price2"] = pd.to_numeric(df_display["price2"], errors="coerce").fillna(0.0)

        df_display["strike1"] = pd.to_numeric(df_display["strike1"], errors="coerce")
        df_display["strike2"] = pd.to_numeric(df_display["strike2"], errors="coerce").fillna(0.0)

        # 计算成本（price1 - price2）* 100
        df_display["成本"] = ((df_display["price1"] - df_display["price2"]).fillna(df_display["price1"])) * 100

        # 计算最大收益
        df_display["最大收益"] = np.where(
            df_display["type"] == "Bull Call Spread",
            (df_display["strike2"] - df_display["strike1"]) * 100 - df_display["成本"],
            df_display["price1"] * 100
        )

        # 防止成本为0导致除零错误
        df_display["成本"] = df_display["成本"].replace(0, np.nan)

        # 计算回报率，空值用0代替
        df_display["回报率"] = (df_display["最大收益"] / df_display["成本"]).round(2).fillna(0.0)

        # 计算策略评分，简单加权示范
        df_display["策略评分"] = (df_display["回报率"] * 0.6 + df_display["最大收益"] / 100 * 0.4).round(1)

        st.dataframe(df_display[["type", "strike1", "strike2", "成本", "最大收益", "回报率", "策略评分"]])
    else:
        st.info("尚未添加任何策略。")

st.caption("⚠️ 本工具为教学与模拟用途，不构成投资建议。")
