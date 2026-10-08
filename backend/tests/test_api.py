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
