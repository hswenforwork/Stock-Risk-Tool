"""執行回測 API 的端到端測試。"""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_run_backtest_returns_performance_report():
    response = client.post("/api/backtests", json={"initial_capital": 1_000_000})

    assert response.status_code == 200
    report = response.json()
    assert report["initial_capital"] == 1_000_000
    assert isinstance(report["total_return"], float)
    assert report["final_equity"] > 0


def test_invalid_settings_are_rejected():
    response = client.post("/api/backtests", json={"initial_capital": -1})

    assert response.status_code == 422


def test_report_includes_trades():
    response = client.post("/api/backtests", json={"initial_capital": 1_000_000, "lot": "board"})

    trades = response.json()["trades"]
    assert trades, "示範策略在示範行情上應該有成交"
    assert {"date", "action", "shares", "price", "fee", "tax", "delayed"} <= trades[0].keys()
    assert all(t["shares"] % 1000 == 0 for t in trades)


def test_start_date_before_odd_lot_trading_is_rejected_with_reason():
    response = client.post(
        "/api/backtests", json={"initial_capital": 1_000_000, "start_date": "2020-01-02"}
    )

    assert response.status_code == 422
    assert "2020-10-26" in response.text


def test_backtest_accepts_handwritten_strategy_json():
    strategy = {
        "version": 1,
        "entry_ratios": [0.5, 0.5],
        "rules": [
            {"action": "entry", "condition": {"type": "close_vs_value", "op": "above", "value": 0}},
            {"action": "add", "condition": {"type": "close_vs_value", "op": "above", "value": 0}},
        ],
    }

    response = client.post(
        "/api/backtests", json={"initial_capital": 1_000_000, "strategy": strategy}
    )

    actions = [(t["action"], t["batch"]) for t in response.json()["trades"]]
    assert actions == [("entry", 1), ("add", 2)]


def test_invalid_strategy_is_rejected_with_reason():
    strategy = {
        "version": 1,
        "entry_ratios": [0.5, 0.3],
        "rules": [
            {"action": "entry", "condition": {"type": "close_vs_value", "op": "above", "value": 0}}
        ],
    }

    response = client.post(
        "/api/backtests", json={"initial_capital": 1_000_000, "strategy": strategy}
    )

    assert response.status_code == 422
    assert "進場比例合計必須是 100%" in response.text


def test_sample_strategy_uses_layers_and_exit_batches():
    response = client.post("/api/backtests", json={"initial_capital": 1_000_000})

    actions = {t["action"] for t in response.json()["trades"]}
    assert {"entry", "add", "exit"} <= actions
