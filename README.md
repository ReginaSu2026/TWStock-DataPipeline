<div align="center">

# 📈 台股籌碼與技術面資料庫建置專案
### TWStock Data Pipeline

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MariaDB](https://img.shields.io/badge/MariaDB-10.11-003545?style=for-the-badge&logo=mariadb&logoColor=white)](https://mariadb.org/)
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-Deployed-222222?style=for-the-badge&logo=github&logoColor=white)](https://ReginaSu2026.github.io/TWStock-DataPipeline/)


<p align="center">
  <b>自動化台股資料 Pipeline | 自建 MariaDB 籌碼資料庫 | 策略選股分析</b>
</p>

</div>

---

## 📌 專案簡介 (Project Overview)

本專案建置一個自動化的 **Data Pipeline**[cite: 1]，定時擷取台灣股市之每日個股價量資訊與三大法人（外資、投信、自營商）籌碼數據[cite: 1]。

資料處理後自動結構化寫入自建之 **MariaDB 資料庫**[cite: 1]，確保數據的完整性與非重複性（Constraint Validation）[cite: 1]，提供後續量化策略回測（如：投信連買 + 布林通道突破）與 Power BI 視覺化分析之基礎[cite: 1]。

---

## 🛠️ 技術架構 (Tech Stack)

| 領域 | 使用技術 / 套件 | 說明 |
| :--- | :--- | :--- |
| **程式語言** | `Python 3.12` | 核心 Data Pipeline 邏輯開發 |
| **資料處理** | `Pandas`, `NumPy` | 數據清洗、時序正規化與籌碼指標計算 |
| **資料庫** | `MariaDB`, `SQLAlchemy`, `PyMySQL` | 關係型資料庫儲存與 ORM 操作[cite: 1] |
| **版本控制** | `Git`, `GitHub` | CI/CD 流程與專案版本管控[cite: 1] |

---

## 🗄️ Database Schema 規劃

資料庫設計包含兩張核心資料表，並透過複合主鍵 `(stock_id, date)` 避免重複寫入[cite: 1]：

### 1. `daily_price` (每日價量表)
> 紀錄個股每日開高低收與成交量數據[cite: 1]。

| 欄位名稱 | 型別 | 說明 |
| :--- | :--- | :--- |
| `stock_id` **(PK)** | `VARCHAR(10)` | 股票代碼 (如: 2330)[cite: 1] |
| `date` **(PK)** | `DATE` | 交易日期 (YYYY-MM-DD)[cite: 1] |
| `open` / `high` / `low` / `close` | `DECIMAL(8,2)` | 開高低收價格[cite: 1] |
| `volume` | `BIGINT` | 成交股數[cite: 1] |

### 2. `institutional_investor` (三大法人籌碼表)
> 紀錄外資、投信與自營商每日買賣超股數[cite: 1]。

| 欄位名稱 | 型別 | 說明 |
| :--- | :--- | :--- |
| `stock_id` **(PK)** | `VARCHAR(10)` | 股票代碼[cite: 1] |
| `date` **(PK)** | `DATE` | 交易日期[cite: 1] |
| `foreign_buy` | `BIGINT` | 外資買賣超股數[cite: 1] |
| `investment_buy` | `BIGINT` | 投信買賣超股數[cite: 1] |
| `dealer_buy` | `BIGINT` | 自營商買賣超股數[cite: 1] |

---

## 💡 策略應用範例 (Strategy Concept)

利用本資料庫架構，可輕鬆執行交集篩選策略：
* **籌碼點火**：近 3 日投信累計買超 $> 0$ 且 外資持續加碼。
* **技術突破**：個股收盤價創近 60 日新高或突破布林通道上軌。
* **流動性濾網**：5 日平均成交量 $> 500$ 張，避開殭屍股。

---

## 🌐 專案成果與展示 (Deployment)

> 🔗 **專案說明網頁**：[點此造訪 GitHub Pages 網頁展示](https://ReginaSu2026.github.io/TWStock-DataPipeline/)

<div align="center">
  <i>Developed by ReginaSu2026</i>
</div>