from __future__ import annotations
import time
import threading
import datetime as dt
import statistics
from typing import List, Dict, Optional

import numpy as np
import yaml
from zoneinfo import ZoneInfo

from TradingBot import TradingBot
from NewsCrawler import NewsCrawler
from SentimentAnalyzer import SentimentAnalyzer
from TradeLogger import TradeLogger

# ───── 시간 설정 (변경 불가) ───────────────────────────
ET            = ZoneInfo("US/Eastern")
MARKET_OPEN   = dt.time(9, 30, tzinfo=ET)
MARKET_CLOSE  = dt.time(16, 0, tzinfo=ET)
# ───────────────────────────────────────────────────────

# ───── 기본 설정값 (config.yaml에서 재정의 가능) ───────
DEFAULT_SYMBOLS           = ["AAPL", "MSFT", "AMZN"]
DEFAULT_BUY_UNIT_USD      = 100
DEFAULT_MOMENTUM_BARS     = 3
DEFAULT_RSI_PERIOD        = 14
DEFAULT_TEST_MODE         = True
DEFAULT_INTERVAL_SEC      = 60
DEFAULT_IDLE_INTERVAL_SEC = 30 * 60
# ───────────────────────────────────────────────────────

# ─── Logger 시작 잔액 설정 (config.yaml에서 재정의 불가) ────
DEFAULT_START_CASH_USD    = 430
# ───────────────────────────────────────────────────────

class AutoTrader:
    def __init__(
        self,
        *,
        stop_event: threading.Event,
        config_path: str = "config.yaml",
        symbols: Optional[List[str]] = None,
    ) -> None:
        self.stop_event = stop_event

        # config.yaml 로드
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        # TradingBot 초기화 (API 설정)
        self.bot = TradingBot(config_path=config_path)

        # Logger 연동 (기본 USD 단위 시작 잔액 전달)
        self.bot.logger = TradeLogger(
            log_dir="logs",
            initial_cash=DEFAULT_START_CASH_USD,
            currency="USD",
        )

        # 사용자 정의 가능한 설정
        self.symbols           = cfg.get("SYMBOLS", symbols or DEFAULT_SYMBOLS)
        self.buy_unit_usd      = cfg.get("BUY_UNIT_USD", DEFAULT_BUY_UNIT_USD)
        self.momentum_bars     = cfg.get("MOMENTUM_BARS", DEFAULT_MOMENTUM_BARS)
        self.rsi_period        = cfg.get("RSI_PERIOD", DEFAULT_RSI_PERIOD)
        self.test_mode         = cfg.get("TEST_MODE", DEFAULT_TEST_MODE)
        self.interval_sec      = cfg.get("INTERVAL_SEC", DEFAULT_INTERVAL_SEC)
        self.idle_interval_sec = cfg.get("IDLE_INTERVAL_SEC", DEFAULT_IDLE_INTERVAL_SEC)

        # 내부 상태
        self.soldout        = {s: False for s in self.symbols}
        self._last_idle_msg = 0.0

    # ─── 4-Factor 스코어 계산 ───────────────────────────
    def compute_scores(
        self,
        *,
        sym: str,
        sentiment: int,
        price_bars: List[Dict],
    ) -> Dict[str, int]:
        score = {"S": sentiment, "M": 0, "R": 0}

        # 1) 가격 Momentum
        if len(price_bars) >= self.momentum_bars * 2:
            last = [b["last"] for b in price_bars[: self.momentum_bars]]
            prev = [b["last"] for b in price_bars[self.momentum_bars : self.momentum_bars * 2]]
            if statistics.mean(last) > statistics.mean(prev):
                score["M"] = +1
            elif statistics.mean(last) < statistics.mean(prev):
                score["M"] = -1

        # 2) RSI
        if len(price_bars) >= self.rsi_period + 1:
            closes   = np.array([b["last"] for b in price_bars[: self.rsi_period + 1]])
            deltas   = np.diff(closes)
            gains    = np.where(deltas > 0, deltas, 0.0)
            losses   = np.where(deltas < 0, -deltas, 0.0)
            avg_gain = gains[-self.rsi_period :].mean()
            avg_loss = losses[-self.rsi_period :].mean()
            rsi      = 100 - 100 / (1 + (avg_gain / (avg_loss + 1e-9)))
            if rsi < 30:
                score["R"] = +1
            elif rsi > 70:
                score["R"] = -1

        score["total"] = score["S"] * 0.2 + score["M"] * 1.2 + score["R"] * 0.6
        return score

    # ─── 매매 결정 ─────────────────────────────────────
    def decide_trade(self, total: float, holdings: int) -> str:
        if total >= 1.0:
            return "buy"
        if total <= -1.0 and holdings > 0:
            return "sell"
        return "hold"

    # ─── 루프 한 번 ────────────────────────────────────
    def loop_once(self) -> None:
        now        = dt.datetime.now(ET)
        is_weekend = now.weekday() >= 5
        in_session = (MARKET_OPEN <= now.time() <= MARKET_CLOSE) and not is_weekend

        # 장외/주말 시 TEST_MODE=False 면 대기
        if not in_session and not self.test_mode:
            if now.timestamp() - self._last_idle_msg >= self.idle_interval_sec:
                reason = "주말" if is_weekend else "장외시간"
                self.bot.send_message(f"⏳ AutoTrader 대기 모드 ({reason})")
                self._last_idle_msg = now.timestamp()
            self.stop_event.wait(timeout=5)
            return

        # 1) 뉴스 크롤링
        self.bot.send_message("🤖 NewsCrawler 작동하는 중...")
        csv_paths = NewsCrawler(self.symbols)

        # 1.1) 감정분석용 CSV 생성
        self.bot.send_message("🤖 SentimentAnalyzer 작동하는 중...")
        from SentimentAnalyzer import get_sentiment_analysis
        get_sentiment_analysis(data_dir="news", out_dir="sentiment")

        # 1.2) sentiment 파일 경로 구성
        from pathlib import Path
        sentiment_paths = [
            Path("sentiment") / f"{Path(p).stem}_sentiment.csv"
            for p in csv_paths
        ]

        # 1.3) 종목별 종합 감정 점수 계산
        sentiments = {
            sym: SentimentAnalyzer(str(path))
            for sym, path in zip(self.symbols, sentiment_paths)
        }

        # 2) 계좌 현금·환율·보유 조회
        summary  = self.bot.get_account_summary()
        usdkrw   = summary.get("rate", 0) or 0
        cash_usd = self.bot.get_usd_balance() if usdkrw else 0
        holdings = self.bot.get_stock_balance()

        # 3) 차트 데이터 조회
        bars_map = {
            sym: self.bot.get_chart_data(code=sym, count=120)
            for sym in self.symbols
        }

        # ─── 4) 종목별 분석 및 주문 ───────────────────────
        for sym in self.symbols:
            tic = time.time()

            bars       = bars_map.get(sym, [])
            score_data = self.compute_scores(
                sym=sym,
                sentiment=sentiments.get(sym, 0),
                price_bars=bars,
            )
            total  = score_data["total"]
            action = self.decide_trade(total, holdings.get(sym, 0))

            # 점수 로그
            self.bot.send_message(
                f"📊 {sym} 분석 결과 : S {score_data['S'] * 0.2}, "
                f"M {score_data['M'] * 1.2}, R {score_data['R'] * 0.6} "
                f"→ 합계 {total} → {action}"
            )

            price = bars[0]["last"] if bars else 0.0

            # ── 매수 로직 ───────────────────────────────
            if action == "buy":
                if holdings.get(sym, 0) > 0:
                    self.bot.send_message(
                        f"🚫 {sym} 매수 생략 : 이미 {holdings[sym]}주 보유 중"
                    )
                    continue

                qty_planned = int(self.buy_unit_usd / price)
                if qty_planned == 0:
                    self.bot.send_message(
                        f"🚫 제한보다 1주 가격이 높습니다 "
                        f"(제한 = {self.buy_unit_usd} USD, 1주 가격 = {price:.2f} USD)"
                    )
                    continue

                need_usd = qty_planned * price

                if self.test_mode:
                    self.bot.send_message(
                        f"[TEST MODE] BUY: {sym} {qty_planned}주 @ {price:.2f}"
                    )
                else:
                    if self.bot.buy("NASD", sym, qty_planned, price):
                        cash_usd -= need_usd

            elif action == "sell" and holdings.get(sym, 0) > 0 and price > 0:
                qty = holdings[sym]
                if self.test_mode:
                    self.bot.send_message(
                        f"[TEST MODE] SELL: {sym} {qty:.4f}주 @ {price:.2f}"
                    )
                else:
                    if self.bot.sell("NASD", sym, qty, price):
                        self.soldout[sym] = True

            elapsed = time.time() - tic
            if elapsed < 1:
                self.stop_event.wait(timeout=1 - elapsed)

        # 5) 자산 스냅샷 기록
        total_stock_val = 0.0
        for sym, bars in bars_map.items():
            if not bars:
                continue
            last_price = bars[0]["last"]
            qty        = holdings.get(sym, 0)
            total_stock_val += last_price * qty

        if self.bot.logger:
            self.bot.logger.log_snapshot(
                cash=cash_usd,
                stock_value=total_stock_val
            )

    # ─── 메인 루프 ─────────────────────────────────────
    def run(self) -> None:
        mode = "테스트 모드" if self.test_mode else "실거래 모드"
        self.bot.send_message(f"🚀 AutoTrader 루프 시작 ({mode})")
        while not self.stop_event.is_set():
            start = time.time()
            try:
                self.loop_once()
            except Exception as e:
                self.bot.send_message(f"⚠️ 루프 예외: {e}")

            elapsed = time.time() - start
            if elapsed < self.interval_sec:
                self.stop_event.wait(timeout=self.interval_sec - elapsed)

        self.bot.send_message("🛑 AutoTrader 종료 완료")


if __name__ == "__main__":
    import signal

    STOP = threading.Event()
    signal.signal(signal.SIGINT, lambda s, f: STOP.set())

    trader = AutoTrader(stop_event=STOP)
    trader.run()
