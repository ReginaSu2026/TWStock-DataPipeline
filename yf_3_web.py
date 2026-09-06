from concurrent.futures import ThreadPoolExecutor
import time

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from FinMind.data import DataLoader
#本程式是一個台股自動化選股與量化篩選工具，旨在結合技術指標與外資籌碼面，自台股上市櫃股票中篩選出具備「回檔整理」或「即將突破」潛力的標的。
#只掃描成交量前 300 名股票，並以價格區間與技術指標判斷策略訊號
#訊號觸發與輸出：判定符合特定策略（回檔、突破前兆、外資連買）的股票並列印結果

#多頭回檔訊號 (PullbackSignal)條件：均線呈多頭排列 + 股價離 20 日線 0~5% 內 + 5日乖離率介於 0~3.5% + KD 之 K 值 $\le$ 70。目的：尋找強勢多頭格局中，拉回至支撐位置的買點。
#最終回檔+外資連買訊號 (FinalPullbackSignal)
#條件：滿足 100~250 元池的回檔條件 (Pullback100250) 且 外資連續 2 天買超 (ForeignBuy2Days)。
#目的：結合技術面回檔與籌碼面法人護盤，提高勝率。

#布林壓縮+量縮訊號 (PreBreakoutSignal)
#條件：成交量前 300 大 + 股價介於 100~250 元 + 股價大於 MA5 + 布林寬度 BB_Width < 0.20 + 當日成交量為 20 日均量的 90% 以下 (< 0.90)。
#目的：捕捉熱門股在窄幅震盪、極致量縮後的即將變盤突破點。





# 三個原始程式的共用設定
PRICE_MIN = 100
PRICE_MAX = 250
TOP_VOLUME_LIMIT = 300
SCAN_WORKERS = 8
FINMIND_INTERVAL_SECONDS = 0.5

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
    page_title="Bloomstx台股策略雷達",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stAppViewContainer"] { background: #fffdfb; }
    h1, h2, h3,
    [data-testid="stHeading"] {
        color: #7c4a36 !important;
        letter-spacing: 0;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #fff8f4 0%, #ffffff 100%);
        border: 1px solid #f2d8ce;
        border-radius: 14px;
        padding: 1rem 1.1rem;
    }
    [data-testid="stMetricLabel"] { color: #9c5b43; }
    [data-testid="stMetricValue"] { color: #4b342b !important; }
    [data-testid="stDataFrame"] { border: 1px solid #eadfd9; border-radius: 12px; }
    .hero-note { color: #765f57; font-size: 1rem; margin-bottom: 1.2rem; }
    [data-testid="stCaptionContainer"] { color: #765f57 !important; }
    [data-baseweb="tab-list"] [role="tab"],
    [data-baseweb="tab"],
    [role="tab"] {
        color: #765f57 !important;
        opacity: 1 !important;
    }
    [data-baseweb="tab-list"] [role="tab"] *,
    [data-baseweb="tab"] *,
    [role="tab"] * {
        color: inherit !important;
    }
    [data-baseweb="tab-list"] [role="tab"][aria-selected="true"] {
        color: #9c5b43 !important;
        font-weight: 700;
    }

    [data-theme="dark"] [data-testid="stAppViewContainer"],
    [data-theme="dark"] .stApp {
        background: #15191f;
    }
    [data-theme="dark"] h1,
    [data-theme="dark"] h2,
    [data-theme="dark"] h3 {
        color: #ffb4c1 !important;
    }
    [data-theme="dark"] [data-testid="stHeading"] {
        color: #ffd6dc !important;
    }
    [data-theme="dark"] .hero-note,
    [data-theme="dark"] [data-testid="stCaptionContainer"] {
        color: #c4ccd4;
    }
    [data-theme="dark"] [data-testid="stMetric"] {
        background: linear-gradient(135deg, #2b1d24 0%, #20262d 100%);
        border-color: #713344;
    }
    [data-theme="dark"] [data-testid="stMetricLabel"] {
        color: #ffb4c1;
    }
    [data-theme="dark"] [data-testid="stMetricValue"],
    [data-theme="dark"] [data-testid="stMetricDelta"] {
        color: #f5f7fa !important;
    }
    [data-theme="dark"] [data-baseweb="tab-list"] [role="tab"] {
        color: #f3d6dc !important;
    }
    [data-theme="dark"] [data-baseweb="tab-list"] [role="tab"] * {
        color: #f3d6dc !important;
    }
    [data-theme="dark"] [data-testid="stDataFrame"] {
        border-color: #4b3039;
    }
    [data-theme="dark"] [data-testid="stSidebar"] {
        background: #1d232a;
        border-right: 1px solid #343c45;
    }
    [data-theme="dark"] [data-testid="stSidebar"] h1,
    [data-theme="dark"] [data-testid="stSidebar"] h2,
    [data-theme="dark"] [data-testid="stSidebar"] h3 {
        color: #ffd6dc;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def to_number(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def fetch_market_quotes():
    """取得上市櫃最新行情、名稱與成交量。"""
    endpoints = [
        (
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            ".TW", "Code", "Name", "ClosingPrice", "TradeVolume",
            "OpeningPrice", "HighestPrice", "LowestPrice",
        ),
        (
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
            ".TWO", "SecuritiesCompanyCode", "CompanyName", "Close",
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
            data = data[data["Code"].str.fullmatch(r"\d+", na=False)]
            for row in data.itertuples():
                ticker = f"{row.Code}{suffix}"
                rows.append({
                    "Ticker": ticker,
                    "Name": "" if str(row.Name).lower() in {"nan", "none"} else str(row.Name).strip(),
                    "Close": row.Close,
                    "Volume": row.Volume,
                    "Open": row.Open,
                    "High": row.High,
                    "Low": row.Low,
                })
        except Exception as error:
            print(f"市場 API 失敗：{error}")

    quotes = {row["Ticker"]: row for row in rows}
    return quotes


def build_candidates(quotes):
    """只建立成交量前 300 大的候選股票池。"""
    volume_pool = sorted(
        quotes,
        key=lambda ticker: quotes[ticker]["Volume"] if pd.notna(quotes[ticker]["Volume"]) else -1,
        reverse=True,
    )[:TOP_VOLUME_LIMIT]
    price_pool = {
        ticker for ticker in volume_pool
        if PRICE_MIN <= quotes[ticker]["Close"] <= PRICE_MAX
    }
    tickers = set(volume_pool)
    return sorted(tickers), price_pool, set(volume_pool)


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

        latest = df.iloc[-1]
        if latest[["MA5", "MA10", "MA20", "BIAS5", "K", "D", "BB_Width", "Vol_MA5", "Vol_MA20"]].isna().any():
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
            "Vol_MA20": float(latest["Vol_MA20"]),
        }
    except Exception:
        return None


def evaluate_signals(metrics, price_pool, volume_pool):
    close = metrics["Close"]
    ma_trend = metrics["MA5"] > metrics["MA10"] > metrics["MA20"]
    pullback = (
        ma_trend
        and 0 <= (close - metrics["MA20"]) / metrics["MA20"] * 100 <= 5
        and 0 <= metrics["BIAS5"] <= 3.5
        and metrics["K"] <= 70
    )
    pullback_100_250 = (
        metrics["Ticker"] in price_pool
        and ma_trend
        and abs((close - metrics["MA5"]) / metrics["MA5"] * 100) <= 5
        and 0 <= metrics["BIAS5"] <= 3.5
        and metrics["K"] <= 70
    )
    prebreakout = (
        metrics["Ticker"] in volume_pool
        and PRICE_MIN <= close <= PRICE_MAX
        and close > metrics["MA5"]
        and metrics["BB_Width"] < 0.20
        and metrics["Volume"] / metrics["Vol_MA20"] < 0.90
    )
    metrics.update({
        "PullbackSignal": pullback,
        "Pullback100250": pullback_100_250,
        "PreBreakoutSignal": prebreakout,
    })
    return metrics


def foreign_buy_two_days(stock_id):
    try:
        today = pd.Timestamp.today()
        data = finmind_loader.taiwan_stock_institutional_investors(
            stock_id=stock_id,
            start_date=(today - pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
        )
        required = {"date", "name", "buy", "sell"}
        if not required.issubset(data.columns):
            return False
        data = data[data["name"].eq("Foreign_Investor")].copy()
        if data.empty:
            return False
        data["buy"] = pd.to_numeric(data["buy"], errors="coerce")
        data["sell"] = pd.to_numeric(data["sell"], errors="coerce")
        daily = data.dropna(subset=["buy", "sell"]).groupby("date")[["buy", "sell"]].sum()
        net = (daily["buy"] - daily["sell"]).sort_index(ascending=False)
        return len(net) >= 2 and net.iloc[0] > 0 and net.iloc[1] > 0
    except Exception:
        return False


def scan_market():
    quotes = fetch_market_quotes()
    if not quotes:
        return None, 0, 0, 0
    candidates, price_pool, volume_pool = build_candidates(quotes)

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as executor:
        metric_rows = list(executor.map(lambda ticker: calculate_metrics(ticker, quotes.get(ticker, {})), candidates))
    metric_rows = [row for row in metric_rows if row]
    results = [evaluate_signals(row, price_pool, volume_pool) for row in metric_rows]

    for row in results:
        row["ForeignBuy2Days"] = False
        if row["Pullback100250"]:
            time.sleep(FINMIND_INTERVAL_SECONDS)
            row["ForeignBuy2Days"] = foreign_buy_two_days(row["Ticker"].rsplit(".", 1)[0])
        row["FinalPullbackSignal"] = row["Pullback100250"] and row["ForeignBuy2Days"]

    if not results:
        return None, len(candidates), len(price_pool), len(volume_pool)
    output = pd.DataFrame(results)
    output["Name"] = output["Name"].replace({"": "中文名稱未取得", "nan": "中文名稱未取得"})
    return output, len(candidates), len(price_pool), len(volume_pool)


def render_table(frame):
    columns = [
        "Ticker", "Name", "Close", "MA5", "MA10", "MA20", "BIAS5",
        "K", "D", "BB_Width", "PullbackSignal", "FinalPullbackSignal",
        "PreBreakoutSignal",
    ]
    display_columns = {
        "Ticker": "股票代號", "Name": "股票名稱", "Close": "收盤價",
        "MA5": "5日均線", "MA10": "10日均線", "MA20": "20日均線",
        "BIAS5": "5日乖離率(%)", "K": "KD-K值", "D": "KD-D值",
        "BB_Width": "布林寬度", "PullbackSignal": "回檔訊號",
        "FinalPullbackSignal": "外資連買回檔", "PreBreakoutSignal": "突破前兆",
    }
    shown = frame[columns].rename(columns=display_columns).copy()
    shown["股票代號"] = shown["股票代號"].map(
        lambda ticker: f"https://finance.yahoo.com/quote/{ticker}/analysis/"
    )
    return shown


def table_config():
    return {
        "股票代號": st.column_config.LinkColumn(
            "股票代號",
            display_text=r".*/quote/([^/]+)/analysis/",
            help="開啟 Yahoo Finance 技術分析頁面",
        ),
        "收盤價": st.column_config.NumberColumn("收盤價", format="%.2f"),
        "5日均線": st.column_config.NumberColumn("5日均線", format="%.2f"),
        "10日均線": st.column_config.NumberColumn("10日均線", format="%.2f"),
        "20日均線": st.column_config.NumberColumn("20日均線", format="%.2f"),
        "5日乖離率(%)": st.column_config.NumberColumn("5日乖離率(%)", format="%.2f"),
        "KD-K值": st.column_config.NumberColumn("KD-K值", format="%.2f"),
        "KD-D值": st.column_config.NumberColumn("KD-D值", format="%.2f"),
        "布林寬度": st.column_config.NumberColumn("布林寬度", format="%.2f"),
    }


def main():
    st.title("Bloomstx台股策略雷達")
    st.markdown(
        '<div class="hero-note">用均線排列、KD、布林通道與外資連買條件，快速整理今日值得觀察的股票。</div>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("掃描控制")
        st.caption("資料來源：TWSE、TPEx、Yahoo Finance、FinMind")
        scan_requested = st.button("重新掃描市場", type="primary", use_container_width=True)
        st.divider()
        st.markdown("**目前策略條件**")
        st.write(f"價格區間：{PRICE_MIN} 至 {PRICE_MAX} 元")
        st.write(f"掃描範圍：成交量前 {TOP_VOLUME_LIMIT} 名")
        st.write(f"價格條件：{PRICE_MIN} 至 {PRICE_MAX} 元")

    if scan_requested or "scan_result" not in st.session_state:
        with st.spinner("正在抓取行情、計算技術指標與外資籌碼，請稍候…"):
            st.session_state.scan_result = scan_market()

    output, candidate_count, price_count, volume_count = st.session_state.scan_result
    if output is None:
        st.error("目前無法取得有效市場資料，請稍後重新掃描。")
        return

    signal_mask = output["PullbackSignal"] | output["PreBreakoutSignal"]
    metric_columns = st.columns(5)
    metric_columns[0].metric("有效資料", f"{len(output)} / {candidate_count}")
    metric_columns[1].metric("價格池", f"{price_count} 檔")
    metric_columns[2].metric("成交量池", f"{volume_count} 檔")
    metric_columns[3].metric("回檔訊號", f"{int(output['PullbackSignal'].sum())} 檔")
    metric_columns[4].metric("突破前兆", f"{int(output['PreBreakoutSignal'].sum())} 檔")

    st.caption(f"最後更新：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}　|　點擊表格欄位可排序")
    tabs = st.tabs(["策略總覽", "多頭回檔", "突破前兆", "全部資料"])
    with tabs[0]:
        st.subheader("今日策略候選")
        st.dataframe(
            render_table(output[signal_mask].sort_values("Close", ascending=False)),
            column_config=table_config(), width="stretch", hide_index=True,
        )
    with tabs[1]:
        st.subheader("均線多頭回檔與外資連買")
        pullback = output[output["FinalPullbackSignal"]].sort_values("K")
        if pullback.empty:
            st.info("目前沒有符合回檔與外資連買條件的標的。")
        else:
            st.dataframe(render_table(pullback), column_config=table_config(), width="stretch", hide_index=True)
    with tabs[2]:
        st.subheader("布林壓縮與量縮突破前兆")
        breakout = output[output["PreBreakoutSignal"]].sort_values("BB_Width")
        if breakout.empty:
            st.info("目前沒有符合突破前兆條件的標的。")
        else:
            st.dataframe(render_table(breakout), column_config=table_config(), width="stretch", hide_index=True)
    with tabs[3]:
        st.subheader("全部有效技術資料")
        st.dataframe(
            render_table(output.sort_values("Ticker")),
            column_config=table_config(), width="stretch", hide_index=True,
        )


if __name__ == "__main__":
    main()
