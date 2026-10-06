# Issue 追蹤：GitHub

本 repo 的 issue 與規格（spec）都以 GitHub issue 形式存放。所有操作皆使用 `gh` CLI。

## 慣例

- **建立 issue**：`gh issue create --title "..." --body "..."`。多行內容請使用 heredoc。
- **讀取 issue**：`gh issue view <number> --comments`，用 `jq` 篩選留言，並一併取得標籤。
- **列出 issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，視需要加上 `--label` 與 `--state` 篩選。
- **在 issue 留言**：`gh issue comment <number> --body "..."`
- **新增／移除標籤**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **關閉**：`gh issue close <number> --comment "..."`

Repo 由 `git remote -v` 推得；在 clone 內執行 `gh` 時會自動判斷。

## 將 Pull Request 視為 triage 來源

**將 PR 視為需求來源：否。** _（若本 repo 把外部 PR 當作功能需求處理，請改為 `yes`；`/triage` 會讀取此設定。）_

設為 `yes` 時，PR 會套用與 issue 相同的標籤與狀態，並使用對應的 `gh pr` 指令：

- **讀取 PR**：`gh pr view <number> --comments`，差異則用 `gh pr diff <number>`。
- **列出待 triage 的外部 PR**：`gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，只保留 `authorAssociation` 為 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 者（排除 `OWNER`／`MEMBER`／`COLLABORATOR`）。
- **留言／標籤／關閉**：`gh pr comment`、`gh pr edit --add-label`／`--remove-label`、`gh pr close`。

GitHub 的 issue 與 PR 共用同一組編號，因此單獨的 `#42` 可能是兩者之一：先用 `gh pr view 42` 判斷，失敗再改用 `gh issue view 42`。

## 當 skill 說「發布到 issue 追蹤系統」

建立一個 GitHub issue。

## 當 skill 說「取得相關的 ticket」

執行 `gh issue view <number> --comments`。

## Wayfinding 操作

供 `/wayfinder` 使用。**地圖（map）**是單一 issue，其**子項（child）** issue 即為各個 ticket。

- **地圖**：單一個帶有 `wayfinder:map` 標籤的 issue，內容包含 Notes／Decisions-so-far／Fog 區段。使用 `gh issue create --label wayfinder:map` 建立。
- **子 ticket**：以 GitHub sub-issue 連結到地圖的 issue（透過 `gh api` 呼叫 sub-issues 端點）。若未啟用 sub-issue，則在地圖內容的任務清單中加入該子項，並在子項內容最上方寫上 `Part of #<map>`。標籤：`wayfinder:<type>`（`research`／`prototype`／`grilling`／`task`）。被認領後，ticket 指派給負責推進的開發者。
- **阻擋關係**：使用 GitHub **原生 issue 相依性**，這是正式且在 UI 上可見的表示方式。新增相依：`gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`，其中 `<blocker-db-id>` 是阻擋者的數字**資料庫 id**（`gh api repos/<owner>/<repo>/issues/<n> --jq .id`，**不是** `#number` 或 `node_id`）。GitHub 會回報 `issue_dependencies_summary.blocked_by`（只計尚未關閉的阻擋者，即目前的關卡）。若無法使用相依性功能，則在子項內容最上方加一行 `Blocked by: #<n>, #<n>`。所有阻擋者都關閉後，ticket 即解除阻擋。
- **前線查詢**：列出地圖底下仍開啟的子項（`gh issue list --state open`，範圍限定在地圖的 sub-issue／任務清單），排除仍有開啟中阻擋者（`issue_dependencies_summary.blocked_by > 0`，或 `Blocked by` 行中有開啟中的 issue）或已有負責人的項目；依地圖順序取第一個。
- **認領**：`gh issue edit <n> --add-assignee @me`，作為該工作階段的第一個寫入動作。
- **解決**：`gh issue comment <n> --body "<answer>"`，接著 `gh issue close <n>`，再把一則情境指引（要點＋連結）附加到地圖的 Decisions-so-far。
