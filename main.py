import threading, signal, sys, time
import datetime as dt
from zoneinfo import ZoneInfo
from AutoTrader import AutoTrader
from TradingBot import TradingBot

ET = ZoneInfo("US/Eastern")

# ─── 전역 STOP 이벤트 ───────────────────────────────────────
STOP_EVENT = threading.Event()

# ─── 전역용 Bot 인스턴스 (메시지 전송용) ─────────────────────
BOT = TradingBot(config_path="config.yaml")

# ─── SIGINT 핸들러 ─────────────────────────────────────────
def _sigint_handler(sig, frame):
    """Ctrl+C → 모든 스레드 종료 & 즉시 프로세스 종료"""
    BOT.send_message("🛑 SIGINT 수신 : 즉시 종료")
    STOP_EVENT.set()          # AutoTrader에게도 종료 신호
    sys.exit(0)               # 메인 스레드 강제 종료

signal.signal(signal.SIGINT, _sigint_handler)

# ─── 메인 루프 ──────────────────────────────────────────────
def main():
    while not STOP_EVENT.is_set():
        trader = AutoTrader(stop_event=STOP_EVENT)

        th = threading.Thread(
            target=trader.run,
            name="AutoTrader",
            daemon=True
        )
        th.start()

        # AutoTrader 종료 또는 SIGINT 대기
        while th.is_alive() and not STOP_EVENT.is_set():
            th.join(timeout=1)

        if STOP_EVENT.is_set():
            break

        # AutoTrader 예외 종료 → 30초 뒤 재시작
        BOT.send_message("❌ AutoTrader 종료 : 30초 후 재시작")
        time.sleep(30)

    BOT.send_message("👋 main.py 정상 종료")

if __name__ == "__main__":
    main()
