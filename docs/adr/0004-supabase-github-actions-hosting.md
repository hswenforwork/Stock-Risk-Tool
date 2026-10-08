# 使用 Supabase（PostgreSQL＋登入）、GitHub Actions 每日同步，前端 Vercel、後端 Render 或 Cloud Run

資料庫與登入都交給 Supabase：PostgreSQL 足以承載上市櫃與 ETF 的日 K 與籌碼資料（千萬列等級），內建的 Google 登入也能滿足「不登入可回測、登入才儲存」的需求，不必自建帳號系統。每日資料同步（ADR 0001）用 GitHub Actions 定時執行，排程與程式碼放在同一處，也不必常駐伺服器。前端（React）部署在 Vercel，後端（Python FastAPI）部署在 Render 或 Cloud Run。這些服務大多能在免費額度內起步。

## 後果

登入與資料庫都綁在 Supabase 上，日後要換掉，就得同時遷移資料和使用者帳號。
