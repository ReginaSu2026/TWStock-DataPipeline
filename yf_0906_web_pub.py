from concurrent.futures import ThreadPoolExecutor
import time

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from FinMind.data import DataLoader

# === 參數設定 ===
PRICE_MIN = 100
PRICE_MAX = 250
TOP_VALUE_LIMIT = 200        # 優化 1：改為日成交金額前 200 大
SCAN_WORKERS = 8
FINMIND_INTERVAL_SECONDS = 0.5
MA5_SLOPE_MIN = 0.0
BIAS5_MIN = -1.0
BIAS5_MAX = 5.0
KD_MAX = 80.0
BB_WIDTH_MAX = 0.25
VOLUME_RATIO_MAX = 0.80

WATCH_LIST = [
    "2303.TW", "2317.TW", "3702.TW", "4938.TW", "3231.TW", "2344.TW",
    "2337.TW", "8033.TW", "2481.TW", "6669.TW", "3481.TW", "3515.TW",
    "5483.TWO", "1815.TWO", "2385.TW", "2885.TW", "2912.TW", "2882.TW",
    "2881.TW", "2886.TW", "6757.TW", "2377.TW", "2548.TW", "8926.TW",
    "2375.TW", "2330.TW", "2313.TW", "2449.TW", "2855.TW", "2884.TW",
    "5386.TWO", "8112.TW", "8086.TWO", "8042.TWO", "5522.TW", "5534.TW",
    "2324.TW", "6719.TW",
]

STOCK_NAMES = {
    "2303.TW": "聯電", "2317.TW": "鴻海", "3702.TW": "大聯大", "4938.TW": "和碩",
    "3231.TW": "緯創", "2344.TW": "華邦電", "2337.TW": "旺宏", "8033.TW": "雷虎",
    "2481.TW": "強茂", "6669.TW": "緯穎", "3481.TW": "群創", "3515.TW": "華擘",
    "5483.TWO": "中美晶", "1815.TWO": "富喬", "2385.TW": "群光", "2885.TW": "元大金",
    "2912.TW": "統一超", "2882.TW": "國泰金", "2881.TW": "富邦金", "2886.TW": "兆豐金",
    "6757.TW": "虎航", "2377.TW": "微星", "2548.TW": "華固", "8926.TW": "台汽電",
    "2375.TW": "凱美", "2330.TW": "台積電", "2313.TW": "華通", "2449.TW": "京元",
    "2855.TW": "統一證", "2884.TW": "玉山金", "5386.TWO": "青雲", "8112.TW": "至上",
    "8086.TWO": "宏捷科", "8042.TWO": "金山電", "5522.TW": "遠雄", "5534.TW": "長虹",
    "2324.TW": "仁寶", "6719.TW": "力智",
}

finmind_loader = DataLoader()

st.set_page_config(
    page_title="台股動能選股",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    [data-testid="stMetricValue"] {font-size: 1.7rem;}
    [data-testid="stDataFrame"] {border: 1px solid #dfe5ec; border-radius: 10px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def to_number(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def fetch_market_quotes():
    """取得上市櫃最新行情，並計算日成交金額 (TradeValue)"""
    endpoints = [
        (
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            ".TW", "Code", "Name", "ClosingPrice", "TradeVolume",
            "OpeningPrice", "HighestPrice", "LowestPrice",
        ),
        (
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
            ".TWO", "SecuritiesCompanyCode", "SecuritiesCompanyName", "Close",
            "TradingShares", "Open", "High", "Low",
        ),
    ]
    rows = []
    for url, suffix, code_col, name_col, close_col, volume_col, open_col, high_col, low_col in endpoints:
        try:
            data = pd.DataFrame(requests.get(url, timeout=15).json())
            required = {code_col, close_col, volume_col, open_col, high_col, low_col}
            if not required.issubset(data.columns):
                continue
            data["Code"] = data[code_col].astype(str).str.strip()
            data["Name"] = data[name_col].astype(str).str.strip() if name_col in data else ""
            data["Close"] = to_number(data[close_col])
            data["Volume"] = to_number(data[volume_col])
            data["Open"] = to_number(data[open_col])
            data["High"] = to_number(data[high_col])
            data["Low"] = to_number(data[low_col])
            data["TradeValue"] = data["Close"] * data["Volume"]  # 計算估算成交金額
            
            data = data[data["Code"].str.fullmatch(r"\d+", na=False)]
            for row in data.itertuples():
                ticker = f"{row.Code}{suffix}"
                rows.append({
                    "Ticker": ticker,
                    "Name": "" if str(row.Name).lower() in {"nan", "none"} else str(row.Name).strip(),
                    "Close": row.Close,
                    "Volume": row.Volume,
                    "TradeValue": row.TradeValue,
                    "Open": row.Open,
                    "High": row.High,
                    "Low": row.Low,
                })
        except Exception as error:
            print(f"市場 API 失敗：{error}")

    quotes = {row["Ticker"]: row for row in rows}
    return quotes


def build_candidates(quotes):
    """建立自選股、100~250 元股價池、成交金額前 200 大的聯集"""
    price_pool = {
        ticker for ticker, quote in quotes.items()
        if PRICE_MIN <= quote["Close"] <= PRICE_MAX
    }
    # 優化 1：依成交金額 (TradeValue) 排序
    value_pool = sorted(
        quotes,
        key=lambda ticker: quotes[ticker]["TradeValue"] if pd.notna(quotes[ticker]["TradeValue"]) else -1,
        reverse=True,
    )[:TOP_VALUE_LIMIT]

    tickers = set(WATCH_LIST) | price_pool | set(value_pool)
    return sorted(tickers), price_pool, set(value_pool)


def normalize_history(df, ticker, quote):
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(-1):
            df = df.xs(ticker, axis=1, level=-1)
        else:
            df.columns = df.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not set(required).issubset(df.columns):
        return None
    df = df.dropna(subset=required).copy()
    if quote and len(df) > 0:
        last_index = df.index[-1]
        for column in required:
            if pd.notna(quote.get(column)):
                df.loc[last_index, column] = quote[column]
    return df


def calculate_metrics(ticker, quote):
    try:
        df = yf.download(ticker, period="90d", interval="1d", auto_adjust=False, progress=False, timeout=15)
        df = normalize_history(df, ticker, quote)
        if df is None or len(df) < 30:
            return None

        # 基本技術指標
        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA10"] = df["Close"].rolling(10).mean()
        df["MA20"] = df["Close"].rolling(20).mean()
        df["Vol_MA5"] = df["Volume"].rolling(5).mean()
        df["Vol_MA20"] = df["Volume"].rolling(20).mean()
        df["BIAS5"] = (df["Close"] - df["MA5"]) / df["MA5"] * 100

        low9 = df["Low"].rolling(9).min()
        high9 = df["High"].rolling(9).max()
        rsv = (df["Close"] - low9) / (high9 - low9) * 100
        df["K"] = rsv.ewm(com=2, adjust=False).mean()
        df["D"] = df["K"].ewm(com=2, adjust=False).mean()

        std20 = df["Close"].rolling(20).std()
        df["BB_Width"] = (4 * std20) / df["MA20"]

        # === 優化指標 ===
        # 優化 2：20 日高點突破（前 19 日最高價）
        df["High20_Prev"] = df["High"].shift(1).rolling(19).max()
        
        # 優化 3：5 日均線斜率 (當日 MA5 vs 昨日 MA5 上漲幅)
        df["MA5_Slope"] = (df["MA5"] - df["MA5"].shift(1)) / df["MA5"].shift(1) * 100

        latest = df.iloc[-1]
        if latest[["MA5", "MA10", "MA20", "BIAS5", "K", "D", "BB_Width", "Vol_MA5", "Vol_MA20", "High20_Prev", "MA5_Slope"]].isna().any():
            return None

        return {
            "Ticker": ticker,
            "Name": STOCK_NAMES.get(ticker) or quote.get("Name", "") or ticker.rsplit(".", 1)[0],
            "Close": float(latest["Close"]),
            "MA5": float(latest["MA5"]),
            "MA10": float(latest["MA10"]),
            "MA20": float(latest["MA20"]),
            "BIAS5": float(latest["BIAS5"]),
            "K": float(latest["K"]),
            "D": float(latest["D"]),
            "Vol_Ratio": float(latest["Volume"] / latest["Vol_MA5"]),
            "BB_Width": float(latest["BB_Width"]),
            "Volume": float(latest["Volume"]),
            "Vol_MA5": float(latest["Vol_MA5"]),
            "Vol_MA20": float(latest["Vol_MA20"]),
            "High20_Prev": float(latest["High20_Prev"]),
            "MA5_Slope": float(latest["MA5_Slope"]),
        }
    except Exception:
        return None


def evaluate_signals(metrics, price_pool, value_pool):
    close = metrics["Close"]
    ma_trend = metrics["MA5"] > metrics["MA10"] > metrics["MA20"]
    ma5_uptrend = metrics["MA5_Slope"] > MA5_SLOPE_MIN

    # 1. 均線多頭+強勢拉回（加入均線斜率驗證）
    pullback = (
        ma_trend
        and ma5_uptrend
        and 0 <= (close - metrics["MA20"]) / metrics["MA20"] * 100 <= 5
        and BIAS5_MIN <= metrics["BIAS5"] <= BIAS5_MAX
        and metrics["K"] <= KD_MAX
    )

    # 2. 100~250元強勢拉回
    pullback_100_250 = (
        metrics["Ticker"] in price_pool
        and ma_trend
        and ma5_uptrend
        and abs((close - metrics["MA5"]) / metrics["MA5"] * 100) <= 5
        and BIAS5_MIN <= metrics["BIAS5"] <= BIAS5_MAX
        and metrics["K"] <= KD_MAX
    )

    # 3. 優化 4：飆股突破前兆 (VCP極致量縮 + 創20日新高試探)
    vol_drop_vcp = metrics["Volume"] / metrics["Vol_MA5"] < VOLUME_RATIO_MAX
    breakout_20d = close >= metrics["High20_Prev"]                # 收盤價突破/觸及近20日高點

    prebreakout = (
        metrics["Ticker"] in value_pool
        and PRICE_MIN <= close <= PRICE_MAX
        and close > metrics["MA5"]
        and ma5_uptrend
        and metrics["BB_Width"] < BB_WIDTH_MAX
        and (vol_drop_vcp or breakout_20d)                       # 極致量縮盤整 OR 帶量創新高突破
    )

    metrics.update({
        "PullbackSignal": pullback,
        "Pullback100250": pullback_100_250,
        "PreBreakoutSignal": prebreakout,
        "Breakout_20D": breakout_20d,
    })
    return metrics


def check_institutional_buys(stock_id):
    """優化 5：查詢外資與投信是否連買 2 天"""
    try:
        today = pd.Timestamp.today()
        data = finmind_loader.taiwan_stock_institutional_investors(
            stock_id=stock_id,
            start_date=(today - pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
        )
        required = {"date", "name", "buy", "sell"}
        if not required.issubset(data.columns):
            return False, False

        data["buy"] = pd.to_numeric(data["buy"], errors="coerce")
        data["sell"] = pd.to_numeric(data["sell"], errors="coerce")

        def check_investor(inv_name):
            inv_df = data[data["name"].eq(inv_name)].copy()
            if inv_df.empty:
                return False
            daily = inv_df.dropna(subset=["buy", "sell"]).groupby("date")[["buy", "sell"]].sum()
            net = (daily["buy"] - daily["sell"]).sort_index(ascending=False)
            return len(net) >= 2 and net.iloc[0] > 0 and net.iloc[1] > 0

        foreign_buy = check_investor("Foreign_Investor")
        trust_buy = check_investor("Investment_Trust")

        return foreign_buy, trust_buy
    except Exception:
        return False, False


def main():
    quotes = fetch_market_quotes()
    if not quotes:
        print("無法取得市場行情。")
        return
    candidates, price_pool, value_pool = build_candidates(quotes)
    print(f"聯集候選股：{len(candidates)} 檔，自選股 {len(set(WATCH_LIST))} 檔，100~250 元 {len(price_pool)} 檔，成交金額前 {TOP_VALUE_LIMIT} 大 {len(value_pool)} 檔")

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as executor:
        metric_rows = list(executor.map(lambda ticker: calculate_metrics(ticker, quotes.get(ticker, {})), candidates))
    metric_rows = [row for row in metric_rows if row]
    results = [evaluate_signals(row, price_pool, value_pool) for row in metric_rows]

    print(
        f"技術資料有效：{len(metric_rows)} / {len(candidates)}，"
        f"價格池：{len(price_pool)}，成交金額池：{len(value_pool)}"
    )
    print(
        "技術條件統計："
        f"均線多頭={sum(row['MA5'] > row['MA10'] > row['MA20'] for row in results)}，"
        f"MA5斜率>0%={sum(row['MA5_Slope'] > MA5_SLOPE_MIN for row in results)}，"
        f"拉回技術訊號={sum(row['PullbackSignal'] for row in results)}，"
        f"突破技術訊號={sum(row['PreBreakoutSignal'] for row in results)}"
    )

    for row in results:
        row["ForeignBuy2Days"] = False
        row["TrustBuy2Days"] = False
        # 只要符合拉回或預備突破條件，就調用 API 驗證法人籌碼
        if row["Pullback100250"] or row["PreBreakoutSignal"]:
            time.sleep(FINMIND_INTERVAL_SECONDS)
            f_buy, t_buy = check_institutional_buys(row["Ticker"].rsplit(".", 1)[0])
            row["ForeignBuy2Days"] = f_buy
            row["TrustBuy2Days"] = t_buy

        # 法人連買保留為參考欄位，不再作為技術訊號的必要條件。
        row["FinalPullbackSignal"] = row["Pullback100250"]
        row["FinalBreakoutSignal"] = row["PreBreakoutSignal"]

    print(
        "法人條件統計："
        f"拉回技術通過={sum(row['Pullback100250'] for row in results)}，"
        f"外資連買={sum(row['ForeignBuy2Days'] for row in results)}，"
        f"投信連買={sum(row['TrustBuy2Days'] for row in results)}，"
        f"最終拉回={sum(row['FinalPullbackSignal'] for row in results)}，"
        f"最終突破={sum(row['FinalBreakoutSignal'] for row in results)}"
    )

    if not results:
        st.warning("沒有取得有效技術資料。")
        return

    output = pd.DataFrame(results)
    output["Name"] = output["Name"].replace({"": "中文名稱未取得", "nan": "中文名稱未取得"})
    columns = [
        "Ticker", "Name", "Close", "MA5_Slope", "BIAS5", "K", "BB_Width",
        "Breakout_20D", "TrustBuy2Days", "ForeignBuy2Days", "FinalPullbackSignal", "FinalBreakoutSignal"
    ]
    display_names = {
        "Ticker": "股票代碼",
        "Name": "中文股名",
        "Close": "收盤價",
        "MA5_Slope": "MA5斜率(%)",
        "BIAS5": "BIAS5乖離率(%)",
        "K": "KD-K值",
        "BB_Width": "布林寬度",
        "Breakout_20D": "突破20日高點",
        "TrustBuy2Days": "投信連買2日",
        "ForeignBuy2Days": "外資連買2日",
        "FinalPullbackSignal": "多頭拉回訊號",
        "FinalBreakoutSignal": "突破訊號",
    }

    def display_table(frame, selected_columns):
        return frame[selected_columns].rename(columns=display_names).round(2)

    pullback_top5 = output[output["FinalPullbackSignal"]].copy()
    if not pullback_top5.empty:
        pullback_top5["PullbackStrength"] = (
            pullback_top5["MA5_Slope"] - pullback_top5["BIAS5"].abs()
        )
        pullback_top5 = pullback_top5.sort_values(
            by=["PullbackStrength", "MA5_Slope"],
            ascending=[False, False],
        ).head(5)

    breakout_top5 = output[output["FinalBreakoutSignal"]].copy()
    if not breakout_top5.empty:
        breakout_top5 = breakout_top5.sort_values(
            by=["Breakout_20D", "BB_Width", "MA5_Slope"],
            ascending=[False, True, False],
        ).head(5)

    technical_candidates = output[
        output["Pullback100250"] | output["PreBreakoutSignal"]
    ].copy()
    if not technical_candidates.empty:
        technical_candidates = technical_candidates.sort_values(
            by=["MA5_Slope", "BB_Width"],
            ascending=[False, True],
        ).head(5)
        technical_columns = [
            "Ticker", "Name", "Close", "MA5_Slope", "BIAS5", "K",
            "BB_Width", "TrustBuy2Days", "ForeignBuy2Days",
        ]

    st.title("台股動能選股")
    st.caption("結合均線拉回、布林壓縮、成交金額與法人籌碼的每日觀察工具")

    metric_columns = st.columns(4)
    metric_columns[0].metric("有效技術資料", f"{len(metric_rows)} / {len(candidates)}")
    metric_columns[1].metric("100~250 元", f"{len(price_pool)} 檔")
    metric_columns[2].metric("成交金額前 200", f"{len(value_pool)} 檔")
    metric_columns[3].metric("技術候選", f"{len(output[output['Pullback100250'] | output['PreBreakoutSignal']])} 檔")

    st.info("法人連買目前作為參考欄位，不會阻擋技術訊號。")

    tabs = st.tabs(["多頭拉回 Top 5", "突破量縮 Top 5", "技術面候選", "全部資料"])
    with tabs[0]:
        st.subheader("多頭拉回訊號")
        if pullback_top5.empty:
            st.info("目前無符合標的")
        else:
            st.dataframe(display_table(pullback_top5, columns), width="stretch", hide_index=True)
    with tabs[1]:
        st.subheader("突破 / 極致量縮訊號")
        if breakout_top5.empty:
            st.info("目前無符合標的")
        else:
            st.dataframe(display_table(breakout_top5, columns), width="stretch", hide_index=True)
    with tabs[2]:
        st.subheader("技術面候選，法人條件僅供參考")
        if technical_candidates.empty:
            st.info("目前沒有通過技術面條件的候選股")
        else:
            st.dataframe(display_table(technical_candidates, technical_columns), width="stretch", hide_index=True)
    with tabs[3]:
        st.subheader("所有有效技術資料")
        st.dataframe(display_table(output, columns), width="stretch", hide_index=True)

    st.caption(f"資料更新時間：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    if st.button("重新掃描", type="primary"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("正在抓取市場行情與技術資料，請稍候..."):
        main()
