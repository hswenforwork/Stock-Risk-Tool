# Stock-Risk-Tool

網頁版台股回測系統：用積木組合交易策略，以台股歷史日 K 驗證策略優劣。

- 規格：[#2](https://github.com/hswenforwork/Stock-Risk-Tool/issues/2)
- 領域用語：[`GLOSSARY.md`](GLOSSARY.md)
- 架構決定：[`docs/adr/`](docs/adr/)

## 專案結構

- `backend/`：Python（FastAPI）。`src/backtest/` 是回測引擎（純計算，不碰資料庫與網路），`src/api/` 是 HTTP API。
- `frontend/`：React＋TypeScript（Vite）。

## 本機開發

需要 [uv](https://docs.astral.sh/uv/) 與 Node.js 22。

```sh
# 後端：http://localhost:8000
cd backend
uv sync
uv run uvicorn api.main:app --app-dir src --reload

# 前端：http://localhost:5173（/api 會轉給後端）
cd frontend
npm install
npm run dev
```

## 檢查

```sh
# 後端
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest

# 前端
cd frontend && npm run lint && npm run build && npm test
```

## 資料來源

行情資料來源：[FinMind](https://finmindtrade.com/)。本網站僅供研究與教育用途，不構成投資建議；過去績效不代表未來。
