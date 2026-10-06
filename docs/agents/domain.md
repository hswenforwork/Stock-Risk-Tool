# 領域文件

說明各工程 skill 在探索程式碼時，應如何使用本 repo 的領域文件。

## 探索前先閱讀

- repo 根目錄的 **`GLOSSARY.md`**，或
- 若 repo 根目錄存在 **`GLOSSARY-MAP.md`**：它會指向各情境（context）各自的 `GLOSSARY.md`，請閱讀與主題相關的每一份。
- **`docs/adr/`**：閱讀與你即將修改區域相關的 ADR。多情境 repo 中，也要查看 `src/<context>/docs/adr/` 裡屬於該情境的決策。

若上述檔案不存在，**直接略過即可**。不要指出它們缺少，也不要事先建議建立。`/domain-modeling` skill（經由 `/grill-with-docs` 與 `/improve-codebase-architecture` 觸發）會在詞彙或決策確定時才按需建立。

## 檔案結構

單一情境 repo（大多數 repo）：

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

多情境 repo（根目錄存在 `GLOSSARY-MAP.md`）：

```
/
├── GLOSSARY-MAP.md
├── docs/adr/                          ← 全系統層級的決策
└── src/
    ├── ordering/
    │   ├── GLOSSARY.md
    │   └── docs/adr/                  ← 該情境專屬的決策
    └── billing/
        ├── GLOSSARY.md
        └── docs/adr/
```

## 使用詞彙表中的用語

當你的產出提到某個領域概念（issue 標題、重構提案、假設、測試名稱）時，請使用 `GLOSSARY.md` 中定義的詞彙。不要改用詞彙表明確避免的同義詞。

若所需概念尚未收錄在詞彙表中，這是一個訊號：可能你在發明專案沒有使用的語言（請重新考慮），也可能確實存在缺口（請記下來交給 `/domain-modeling`）。

## 標示與 ADR 的衝突

若你的產出與既有 ADR 相牴觸，請明確指出，而不是默默推翻：

> _與 ADR-0007（event-sourced orders）相牴觸，但值得重新討論，因為……_
