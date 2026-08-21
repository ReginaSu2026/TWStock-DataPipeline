# 台股籌碼與技術面資料庫建置專案 (TWStock-DataPipeline)

📌 專案簡介
本專案透過 Python 自動化擷取台股價量與籌碼數據，並建構 MariaDB 資料庫進行結構化儲存與策略分析[cite: 1]。

🎯 專案目的
建置自動化 Data Pipeline，依設定頻率定時抓取台股每日價量與三大法人籌碼數據，並結構化存入自建 MariaDB 資料庫，提供後續籌碼面（投信連買）與技術面（布林通道突破）之策略分析與視覺化。

🛠️ 技術棧 (Tech Stack)
- **程式語言**：Python (Pandas, SQLAlchemy, PyMySQL)
- **資料庫**：MariaDB (設定 Primary Key Constraint 確保數據不重複)
- **版本控制與部署**：Git / GitHub / GitHub Pages

🗄️ Database Schema 規劃
資料庫包含兩張核心資料表：
1. `daily_price`：儲存股票開高低收與成交量。
2. `institutional_investor`：儲存外資、投信與自營商買賣超數據。

🌐 專案網頁 (GitHub Pages)
請造訪本專案之 [GitHub Pages 說明網頁](https://ReginaSu2026.github.io/TWStock-DataPipeline/) 觀看詳細展示。