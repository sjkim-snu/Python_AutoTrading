from __future__ import annotations
import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import pandas as pd

KST = ZoneInfo("Asia/Seoul")


class TradeLogger:
    def __init__(
        self,
        log_dir: str = "logs",
        initial_cash: float = 0.0,
        currency: str = "USD",
    ) -> None:
        """
        :param log_dir:      로그 디렉터리
        :param initial_cash: 시작 시점의 현금 (USD)
        :param currency:     통화 단위 표시 ("USD")
        """
        self.dir = Path(log_dir)
        self.dir.mkdir(exist_ok=True)
        self.currency = currency

        # 고정된 파일명 사용
        self.trade_csv = self.dir / "trades.csv"
        self.equity_csv = self.dir / "equity.csv"

        # ── trades.csv 헤더 생성 (파일 없을 때만) ──
        if not self.trade_csv.exists():
            self.trade_csv.write_text(
                "time,symbol,side,qty,price,amount\n", encoding="utf-8"
            )

        # ── equity.csv 헤더 및 시작 잔액 주석 생성 (파일 없을 때만) ──
        if not self.equity_csv.exists():
            with self.equity_csv.open("w", encoding="utf-8", newline="") as f:
                f.write(f"# starting_cash,{initial_cash:.2f}\n")
                f.write("time,cash,stock_value,total_equity,realized_pnl\n")

        self.realized_pnl = 0.0
        # 최초 스냅샷 (stock_value=0, realized_pnl=0)
        self._write_initial_snapshot(initial_cash)

    def _write_initial_snapshot(self, cash: float) -> None:
        t = dt.datetime.now(KST).isoformat(sep=" ", timespec="seconds")
        total = cash
        with self.equity_csv.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([t, f"{cash:.2f}", "0.00", f"{total:.2f}", "0.00"])

    def log_trade(self, *, symbol: str, side: str, qty: float, price: float) -> None:
        amount = qty * price * (1 if side == "buy" else -1)
        if side == "sell":
            self.realized_pnl += -amount

        t = dt.datetime.now(KST).isoformat(sep=" ", timespec="seconds")
        with self.trade_csv.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([t, symbol, side, qty, price, amount])

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

    def draw_graphs(self) -> None:
        if not self.equity_csv.exists():
            print(f"🛑 {self.equity_csv} 가 없습니다. 먼저 로그를 생성하세요.")
            return

        # 주석(#) 건너뛰고 로드
        equity = pd.read_csv(self.equity_csv, comment="#", parse_dates=["time"])
        if equity.empty:
            print("ℹ️ equity.csv 가 비어 있습니다.")
            return

        for col in ["cash", "stock_value", "total_equity", "realized_pnl"]:
            equity[col] = equity[col].astype(float)

        start_time = equity["time"].iloc[0]
        equity["elapsed_min"] = (equity["time"] - start_time).dt.total_seconds() / 60.0
        mn, mx = 0.0, equity["elapsed_min"].max()

        # 1. Total Equity
        plt.figure()
        plt.plot(equity["elapsed_min"], equity["total_equity"])
        plt.title("Total Equity")
        plt.xlabel("Elapsed Time (min)")
        plt.ylabel(f"Amount ({self.currency})")
        plt.xlim(mn, mx)
        plt.tight_layout()

        # 2. Cash vs Stock Value (+ 합산선)
        plt.figure()
        plt.plot(equity["elapsed_min"], equity["cash"], label="Cash")
        plt.plot(equity["elapsed_min"], equity["stock_value"], label="Stock Value")
        plt.plot(
            equity["elapsed_min"],
            equity["cash"] + equity["stock_value"],
            "--",
            label="Cash + Stock",
        )
        plt.title("Cash vs Stock Value")
        plt.xlabel("Elapsed Time (min)")
        plt.ylabel(f"Amount ({self.currency})")
        plt.xlim(mn, mx)
        plt.legend()
        plt.tight_layout()

        # 3. Cumulative Realized P/L
        plt.figure()
        plt.plot(equity["elapsed_min"], equity["realized_pnl"])
        plt.title("Cumulative Realized P/L")
        plt.xlabel("Elapsed Time (min)")
        plt.ylabel(f"P/L ({self.currency})")
        plt.xlim(mn, mx)
        plt.tight_layout()

        # 4. Buy / Sell by Symbol
        trades = pd.read_csv(self.trade_csv, parse_dates=["time"])
        if not trades.empty:
            trades["elapsed_min"] = (
                pd.to_datetime(trades["time"]).dt.tz_localize(KST) - start_time
            ).dt.total_seconds() / 60.0

            syms = trades["symbol"].unique()
            cmap = plt.cm.get_cmap("tab10", len(syms))
            colors = {s: cmap(i) for i, s in enumerate(syms)}

            # Buy
            buy = trades[trades["side"] == "buy"]
            if not buy.empty:
                plt.figure()
                for s in syms:
                    df = buy[buy["symbol"] == s]
                    if df.empty:
                        continue
                    plt.scatter(df["elapsed_min"], df["amount"], label=s, color=colors[s])
                plt.title("Buy Trade Amounts by Symbol")
                plt.xlabel("Elapsed Time (min)")
                plt.ylabel(f"Amount (+buy) ({self.currency})")
                plt.xlim(mn, mx)
                plt.legend()
                plt.tight_layout()

            # Sell
            sell = trades[trades["side"] == "sell"]
            if not sell.empty:
                plt.figure()
                for s in syms:
                    df = sell[sell["symbol"] == s]
                    if df.empty:
                        continue
                    plt.scatter(df["elapsed_min"], df["amount"], label=s, color=colors[s])
                plt.title("Sell Trade Amounts by Symbol")
                plt.xlabel("Elapsed Time (min)")
                plt.ylabel(f"Amount (–sell) ({self.currency})")
                plt.xlim(mn, mx)
                plt.legend()
                plt.tight_layout()

        plt.show()


if __name__ == "__main__":
    logger = TradeLogger("logs")
    logger.draw_graphs()
