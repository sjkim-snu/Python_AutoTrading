from __future__ import annotations
import csv, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import pandas as pd

KST = ZoneInfo("Asia/Seoul")


class TradeLogger:
    def __init__(self, log_dir: str = "logs") -> None:
        self.dir = Path(log_dir)
        self.dir.mkdir(exist_ok=True)
        self.trade_csv = self.dir / "trades.csv"
        self.equity_csv = self.dir / "equity.csv"

        # 파일이 없으면 헤더만 작성
        if not self.trade_csv.exists():
            self.trade_csv.write_text(
                "time,symbol,side,qty,price,amount\n", encoding="utf-8"
            )
        if not self.equity_csv.exists():
            self.equity_csv.write_text(
                "time,cash,stock_value,total_equity,realized_pnl\n", encoding="utf-8"
            )

        self.realized_pnl = 0.0

    # ── 체결 1건 기록 ─────────────────────────────────
    def log_trade(self, *, symbol: str, side: str, qty: float, price: float) -> None:
        amount = qty * price * (1 if side == "buy" else -1)
        if side == "sell":
            self.realized_pnl += -amount

        t = dt.datetime.now(KST).isoformat(sep=" ", timespec="seconds")
        with self.trade_csv.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([t, symbol, side, qty, price, amount])

    # ── 자산 스냅샷 기록 ───────────────────────────────
    def log_snapshot(self, *, cash: float, stock_value: float) -> None:
        total = cash + stock_value
        t = dt.datetime.now(KST).isoformat(sep=" ", timespec="seconds")
        with self.equity_csv.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(
                [
                    t,
                    f"{cash:.2f}",
                    f"{stock_value:.2f}",
                    f"{total:.2f}",
                    f"{self.realized_pnl:.2f}",
                ]
            )

    # ── 그래프 출력 (경과시간 축) ───────────────────────
    def draw_graphs(self) -> None:
        if not self.equity_csv.exists():
            print(f"🛑 {self.equity_csv} 가 없습니다. 먼저 AutoTrader 로그를 생성하세요.")
            return

        equity = pd.read_csv(self.equity_csv, parse_dates=["time"])
        if equity.empty:
            print("ℹ️ equity.csv 가 비어 있습니다. 로그를 쌓은 뒤 다시 실행하세요.")
            return

        num_cols = ["cash", "stock_value", "total_equity", "realized_pnl"]
        equity[num_cols] = equity[num_cols].astype(float)

        # ── 경과 분 계산 ──────────────────────────────
        start_time = equity["time"].iloc[0]
        equity["elapsed_min"] = (equity["time"] - start_time).dt.total_seconds() / 60.0

        # ① Total Equity
        plt.figure()
        plt.plot(equity["elapsed_min"], equity["total_equity"])
        plt.title("Total Equity")
        plt.xlabel("Elapsed Time (min)")
        plt.ylabel("Amount")
        plt.tight_layout()

        # ② Cash vs Stock Value
        plt.figure()
        plt.plot(equity["elapsed_min"], equity["cash"], label="Cash")
        plt.plot(equity["elapsed_min"], equity["stock_value"], label="Stock Value")
        plt.title("Cash vs Stock Value")
        plt.xlabel("Elapsed Time (min)")
        plt.ylabel("Amount")
        plt.legend()
        plt.tight_layout()

        # ③ Cumulative Realized P/L
        plt.figure()
        plt.plot(equity["elapsed_min"], equity["realized_pnl"])
        plt.title("Cumulative Realized P/L")
        plt.xlabel("Elapsed Time (min)")
        plt.ylabel("P/L")
        plt.tight_layout()

        # ④ Individual Trade Amounts
        if self.trade_csv.exists():
            trades = pd.read_csv(self.trade_csv, parse_dates=["time"])
            if not trades.empty:
                trades["time"] = pd.to_datetime(trades["time"], errors="coerce")
                trades["amount"] = trades["amount"].astype(float)
                trades["elapsed_min"] = (
                    trades["time"] - start_time
                ).dt.total_seconds() / 60.0

                plt.figure()
                plt.scatter(trades["elapsed_min"], trades["amount"])
                plt.title("Individual Trade Amounts")
                plt.xlabel("Elapsed Time (min)")
                plt.ylabel("Amount (+buy, –sell)")
                plt.tight_layout()

        plt.show()


# ── 단독 실행용 메인 가드 ─────────────────────────────
if __name__ == "__main__":
    logger = TradeLogger("logs")
    logger.draw_graphs()
