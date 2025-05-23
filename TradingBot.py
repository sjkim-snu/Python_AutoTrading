from __future__ import annotations
import json
import os
import yaml
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from zoneinfo import ZoneInfo
from TradeLogger import TradeLogger 

# ───── 상수 ───────────────────────────────────────────────────
ET        = ZoneInfo("US/Eastern")      # 미국 동부시간 (나스닥)
KST       = ZoneInfo("Asia/Seoul")      # 한국
TOKEN_LIFE = 18 * 3600                   # 토큰 유효 18 h (24 h 안전 마진)

class TradingBot:
    def __init__(
        self,
        config_path: str = "config.yaml",
        buy_percent: float = 0.33,
        target_buy_count: int = 3,
        nasd_list: list[str] | None = None,
        nyse_list: list[str] | None = None,
        amex_list: list[str] | None = None,
    ):
        self._load_config(config_path)

        # 상태 변수
        self.access_token: str       = ""
        self.token_issue_time: dt.datetime | None = None
        self.TOKEN_FILE: Path       = Path("token.json")

        # 매매 파라미터
        self.buy_percent      = buy_percent
        self.target_buy_count = target_buy_count
        self.nasd_list        = nasd_list or []
        self.nyse_list        = nyse_list or []
        self.amex_list        = amex_list or []

        # 저장된 토큰 불러오기
        self._load_saved_token()
        
        # Logger 연동
        self.logger: Optional[TradeLogger] = None

    def _load_config(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)
        self.APP_KEY             = cfg["APP_KEY"]
        self.APP_SECRET          = cfg["APP_SECRET"]
        self.CANO                = cfg["CANO"]
        self.ACNT_PRDT_CD        = cfg["ACNT_PRDT_CD"]
        self.DISCORD_WEBHOOK_URL = cfg["DISCORD_WEBHOOK_URL"]
        self.URL_BASE            = cfg["URL_BASE"]

    def send_message(self, msg: str) -> None:
        now = dt.datetime.now(KST)
        payload = {"content": f"[{now:%Y-%m-%d %H:%M:%S}] {msg}"}
        try:
            requests.post(self.DISCORD_WEBHOOK_URL, data=payload, timeout=3)
        except Exception:
            pass
        
    def _hashkey(self, data: dict) -> str:
        url     = f"{self.URL_BASE}/uapi/hashkey"
        headers = {
            "Content-Type": "application/json",
            "appKey": self.APP_KEY,
            "appSecret": self.APP_SECRET,
        }
        res = requests.post(url, headers=headers, data=json.dumps(data))
        return res.json().get("HASH", "")

    # ─────────────────────────────────────────────────────────
    # 토큰 관리
    # ─────────────────────────────────────────────────────────
    def _save_token(self) -> None:
        blob = {
            "access_token":     self.access_token,
            "token_issue_time": self.token_issue_time.isoformat() if self.token_issue_time else None,
        }
        self.TOKEN_FILE.write_text(json.dumps(blob), encoding="utf-8")

    def _load_saved_token(self) -> None:
        if not self.TOKEN_FILE.exists():
            return
        try:
            blob = json.loads(self.TOKEN_FILE.read_text(encoding="utf-8"))
            self.access_token = blob.get("access_token", "")
            ts = blob.get("token_issue_time")
            if ts:
                t = dt.datetime.fromisoformat(ts)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=ET)
                self.token_issue_time = t
        except Exception:
            pass

    def _request_new_token(self) -> str:
        body = {"grant_type": "client_credentials", "appkey": self.APP_KEY, "appsecret": self.APP_SECRET}
        headers = {"Content-Type": "application/json"}
        url     = f"{self.URL_BASE}/oauth2/tokenP"
        res     = requests.post(url, headers=headers, json=body, timeout=3)
        res.raise_for_status()
        self.access_token     = res.json()["access_token"]
        self.token_issue_time = dt.datetime.now(ET)
        self._save_token()
        self.send_message("🔑 새 Access Token 발급 완료")
        return self.access_token

    def refresh_token_if_needed(self) -> None:
        now = dt.datetime.now(ET)
        t0  = self.token_issue_time

        # 1) 토큰이 없거나 token_issue_time 이 세팅되지 않았으면
        if t0 is None or not self.access_token:
            self.send_message("🔄 Access Token 발급")
            self._request_new_token()
            return

        # 2) timezone 보정 (fromisoformat 으로 불러올 때 tzinfo 누락 시)
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=ET)

        # 3) 남은 수명 확인 (여유 마진 5분 포함)
        elapsed = (now - t0).total_seconds()
        if elapsed >= TOKEN_LIFE - 300:  # 300초 = 5분 여유
            self.send_message("🔄 Access Token 재발급 (만료 예정)")
            self._request_new_token()

    # ─────────────────────────────────────────────────────────
    # 현재가 조회
    # ─────────────────────────────────────────────────────────
    def get_current_price(self, market: str, code: str) -> float:
        self.refresh_token_if_needed()
        headers = {"Content-Type": "application/json", "authorization": f"Bearer {self.access_token}",
                   "appKey": self.APP_KEY, "appSecret": self.APP_SECRET, "tr_id": "HHDFS00000300"}
        params = {"AUTH": "", "EXCD": market, "SYMB": code}
        url    = f"{self.URL_BASE}/uapi/overseas-price/v1/quotations/price"
        last   = requests.get(url, headers=headers, params=params).json()["output"]["last"]
        price  = float(last)
        self.send_message(f"📈 {code} 현재가 {price}")
        return price

    # ─────────────────────────────────────────────────────────
    # 분봉 차트 데이터 조회
    # ─────────────────────────────────────────────────────────
    def get_chart_data(
        self,
        market: str = "NAS",
        code:   str = "AAPL",
        interval: str = "1",
        count:   int = 120,
    ) -> List[Dict[str, Any]]:
        self.refresh_token_if_needed()
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.APP_KEY,
            "appSecret": self.APP_SECRET,
            "tr_id": "HHDFS76950200",  # 분봉 조회용 TR ID
        }
        params = {
            "AUTH": "", "EXCD": market, "SYMB": code,
            "TIMETYPE": "1", "CNT": str(count), "INTERVAL": interval,
        }
        url = f"{self.URL_BASE}/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"

        # ① 응답 JSON 구조 확인
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        data = resp.json()
        raw = data.get("output2", [])
        if raw:
            print("[DEBUG] chart data fields:", raw[0].keys())

        chart = []
        for it in raw:
            # 실제 필드명 'tymd' + 'xhms' 조합으로 datetime 생성
            date = it.get("tymd") or it.get("xymd")
            hms  = it.get("xhms") or it.get("khms")
            if not date or not hms:
                continue
            dt_obj = dt.datetime.strptime(date + hms, "%Y%m%d%H%M%S").replace(tzinfo=ET)

            chart.append({
                "time": dt_obj.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "open": float(it.get("open", 0)),
                "high": float(it.get("high", 0)),
                "low":  float(it.get("low", 0)),
                "last": float(it.get("last", 0)),
                "evol": int(it.get("evol", 0)),
            })
        self.send_message(f"🗂️ {code} 차트 {len(chart)}개 조회 완료")
        return chart

    # ─────────────────────────────────────────────────────────
    # 체결 추이 조회
    # ─────────────────────────────────────────────────────────
    def get_trade_intensity(
        self,
        market: str,
        code:   str,
        tday:   str,
    ) -> List[Dict[str, Any]]:
        """
        • market: 'NASD' 등 거래소 코드
        • code:   종목 심볼
        • tday:   조회할 날짜(YYYYMMDD)
        """
        self.refresh_token_if_needed()
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey": self.APP_KEY,
            "appSecret": self.APP_SECRET,
            "tr_id": "HHDFS76200300",
        }
        params = {
            "AUTH": "", "EXCD": market, "SYMB": code, "TDAY": tday
        }
        url  = f"{self.URL_BASE}/uapi/overseas-price/v1/quotations/inquire-ccnl"
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        raw = resp.json().get("output1", [])
        if raw:
            print("[DEBUG] intensity data fields:", raw[0].keys())

        records = []
        for it in raw:
            # 실제 키에 맞춰 조정하세요
            records.append({
                # 필요한 경우 시간 필드도 파싱 가능 (분봉과 동일하게 date+hms 조합)
                "time": it.get("time", ""),
                "vpow": float(it.get("vpow", 0)),
                # "powx": float(it.get("powx", 0)),  # 예시
                # "tcnt": int(it.get("tcnt", 0)),    # 예시
            })
        self.send_message(f"🔍 {code} 체결강도 {len(records)}건 조회 완료")
        return records

    # ─────────────────────────────────────────────────────────
    # 잔고·환율·평가
    # ─────────────────────────────────────────────────────────
    def get_balance(self) -> int:
        self.refresh_token_if_needed()

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey":        self.APP_KEY,
            "appSecret":     self.APP_SECRET,
            "tr_id":         "TTTC8908R",
            "custtype":      "P",
        }
        params = {
            "CANO":            self.CANO,
            "ACNT_PRDT_CD":    self.ACNT_PRDT_CD,
            "PDNO":            "005930",
            "ORD_UNPR":        "0",
            "ORD_DVSN":        "01",
            "CMA_EVLU_AMT_ICLD_YN": "Y",
            "OVRS_ICLD_YN":    "Y",
        }
        url  = f"{self.URL_BASE}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
        cash = int(requests.get(url, headers=headers, params=params)
                   .json()["output"]["ord_psbl_cash"])
        self.send_message(f"💰 현금 {cash:,} KRW")
        return cash

    def get_stock_balance(self) -> dict[str, int]:
        self.refresh_token_if_needed()

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey":        self.APP_KEY,
            "appSecret":     self.APP_SECRET,
            "tr_id":         "JTTT3012R",
            "custtype":      "P",
        }
        params = {
            "CANO":         self.CANO,
            "ACNT_PRDT_CD": self.ACNT_PRDT_CD,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD":   "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        }
        url  = f"{self.URL_BASE}/uapi/overseas-stock/v1/trading/inquire-balance"
        rows = requests.get(url, headers=headers, params=params).json().get("output1", [])
        stock = {r["ovrs_pdno"]: int(r["ovrs_cblc_qty"])
                 for r in rows if int(r["ovrs_cblc_qty"]) > 0}
        self.send_message(f"📦 보유 종목 {stock}")
        return stock

    def get_account_summary(self) -> Dict[str, float]:
        self.refresh_token_if_needed()

        # 1) USD/KRW
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey":        self.APP_KEY,
            "appSecret":     self.APP_SECRET,
            "tr_id":         "CTRP6504R",
        }
        params   = {
            "CANO":            self.CANO,
            "ACNT_PRDT_CD":    self.ACNT_PRDT_CD,
            "OVRS_EXCG_CD":    "NASD",
            "WCRC_FRCR_DVSN_CD": "01",
            "NATN_CD":         "840",
            "TR_MKET_CD":      "01",
            "INQR_DVSN_CD":    "00",
        }
        url_rate = f"{self.URL_BASE}/uapi/overseas-stock/v1/trading/inquire-present-balance"
        usdkrw   = float(requests.get(url_rate, headers=headers, params=params)
                         .json()["output2"][0]["frst_bltn_exrt"])

        # 2) 잔고·평가·손익 조회
        headers["tr_id"] = "JTTT3012R"
        bal = requests.get(
            f"{self.URL_BASE}/uapi/overseas-stock/v1/trading/inquire-balance",
            headers=headers,
            params={
                "CANO":         self.CANO,
                "ACNT_PRDT_CD": self.ACNT_PRDT_CD,
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD":   "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            }
        ).json()

        eval_amt_usd = eval_pnl_usd = 0.0
        for r in bal.get("output1", []):
            qty    = float(r.get("ovrs_cblc_qty", 0))
            ev_amt = float(r.get("ovrs_stck_evlu_amt") or r.get("evlu_amt") or 0)
            if ev_amt == 0 and qty:
                price  = float(r.get("last", 0))
                ev_amt = price * qty
            pnl = float(r.get("frcr_evlu_pfls_amt") or r.get("evlu_pfls_amt") or 0)
            eval_amt_usd += ev_amt
            eval_pnl_usd += pnl

        cash_krw        = self.get_balance()
        eval_amt_krw    = eval_amt_usd * usdkrw
        eval_pnl_krw    = eval_pnl_usd * usdkrw
        total_asset_krw = cash_krw + eval_amt_krw

        self.send_message(f"💱 USD/KRW {usdkrw}")
        self.send_message(f"💼 평가금액 {eval_amt_krw:,.0f} KRW / 손익 {eval_pnl_krw:,.0f} KRW")
        self.send_message(f"🧾 총자산 {total_asset_krw:,.0f} KRW")

        return {
            "rate":        usdkrw,
            "eval_amount": eval_amt_krw,
            "eval_pnl":    eval_pnl_krw,
            "total_asset": total_asset_krw,
        }
        
    def get_usd_balance(self) -> float:
        self.refresh_token_if_needed()

        headers = {
            "Content-Type":  "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey":        self.APP_KEY,
            "appSecret":     self.APP_SECRET,
            "tr_id":         "TTTT3012R",
            "custtype":      "P",
        }
        params = {
            "CANO":         self.CANO,
            "ACNT_PRDT_CD": self.ACNT_PRDT_CD,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD":   "",          # ★ 반드시 빈 문자열로! (통화 필터 해제)
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        }

        url  = f"{self.URL_BASE}/uapi/overseas-stock/v1/trading/inquire-balance"
        res  = requests.get(url, headers=headers, params=params, timeout=5).json()

        # output1·2·3 → list 로 정규화
        def _n(x): return x if isinstance(x, list) else ([x] if isinstance(x, dict) else [])
        rows = _n(res.get("output2")) + _n(res.get("output3"))  # ← output3 추가
        if not rows: rows = _n(res.get("output1"))

        cash_keys = (
            "frcr_drwg_psbl_amt_1",  # 출금·주문가능 외화
            "frcr_dncl_amt_2",       # 외화예수금
            "frcr_use_psbl_amt",     # 통합 사용가능
            "ovrs_avlb_ord_amt",
            "frcr_psbl_ord_amt",
            "psbl_ord_amt",
        )

        cash_usd = 0.0
        for r in rows:
            # 일부 응답은 통화코드(crcy_cd) 가 없음 → 금액이 1개라도 잡히면 그대로 사용
            for k in cash_keys:
                v = r.get(k)
                if v and float(v) > 0:
                    cash_usd = float(v)
                    break
            if cash_usd:
                break

        # self.send_message(f"💵 해외 주문가능 잔고 {cash_usd:,.2f} USD")
        return cash_usd

    # ─────────────────────────────────────────────────────────
    # 주문
    # ─────────────────────────────────────────────────────────
    def buy(self, market: str, code: str, qty: int, price: float) -> bool:
        self.refresh_token_if_needed()
        data = {
            "CANO":         self.CANO,
            "ACNT_PRDT_CD": self.ACNT_PRDT_CD,
            "OVRS_EXCG_CD": market,
            "PDNO":         code,
            "ORD_DVSN":     "00",            # ★ 항상 ‘지정가 정수주’ 코드
            "ORD_QTY":      str(qty),        # 정수 문자열
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
        }
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appKey":  self.APP_KEY,
            "appSecret": self.APP_SECRET,
            "tr_id":   "TTTT1002U",          # 미국 매수(정수주) TR
            "custtype": "P",
            "hashkey": self._hashkey(data),
        }
        url = f"{self.URL_BASE}/uapi/overseas-stock/v1/trading/order"
        res = requests.post(url, headers=headers, data=json.dumps(data)).json()
        ok = res.get("rt_cd") == "0"

        if ok:
            # 종목·수량·가격을 자세히 로깅
            self.send_message(f"✅ 매수 성공: {code} {qty:.4f}주 @ {price:.2f} USD")
            if self.logger:                                    # ← Null-check
              self.logger.log_trade(symbol=code,
                              side="buy",
                              qty=qty,
                              price=price)
        else:
            err = res.get("message", "알 수 없는 오류")
            self.send_message(f"❌ 매수 실패: {code} @ {price:.2f} → {err}")

        return ok

    def sell(self, market: str, code: str, qty: int, price: float) -> bool:
        self.refresh_token_if_needed()
        data = {
            "CANO":            self.CANO,
            "ACNT_PRDT_CD":    self.ACNT_PRDT_CD,
            "OVRS_EXCG_CD":    market,
            "PDNO":            code,
            "ORD_DVSN":        "00",
            "ORD_QTY":         str(qty),
            "OVRS_ORD_UNPR":   f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
        }
        headers = {
            "Content-Type": "application/json",
            "authorization":    f"Bearer {self.access_token}",
            "appKey":           self.APP_KEY,
            "appSecret":        self.APP_SECRET,
            "tr_id":            "TTTT1006U",
            "custtype":         "P",
            "hashkey":          self._hashkey(data),
        }
        url = f"{self.URL_BASE}/uapi/overseas-stock/v1/trading/order"
        res = requests.post(url, headers=headers, data=json.dumps(data)).json()
        ok = res.get("rt_cd") == "0"

        if ok:
            self.send_message(f"✅ 매도 성공: {code} {qty:.4f}주 @ {price:.2f} USD")
            if self.logger:                                    # ← Null-check
              self.logger.log_trade(symbol=code,
                              side="sell",
                              qty=qty,
                              price=price)
        else:
            err = res.get("message", "알 수 없는 오류")
            self.send_message(f"❌ 매도 실패: {code} @ {price:.2f} → {err}")

        return ok
