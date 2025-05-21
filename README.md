# 🚀 2025 Python Project

## 📖 Table of Contents
1. 🛠️ 코드 설명 및 구조  
2. 📦 사용 방법
3. 🤖 About Sentiment Analysis
4. 👥 Contributor  

## 🛠️ 1. 코드 설명 및 구조

### 📰 NewsCrawler.py

1. **역할:**  
   - 지정된 주식 심볼에 대해  
     1. **Yahoo Finance API** → 뉴스 데이터 조회  
     2. **Finviz 웹 크롤링** → 뉴스 테이블 파싱  
     3. 두 소스로부터 **통합 DataFrame** 생성  
     4. CSV 파일로 저장 후 파일 경로 리스트 반환  
   - 단독 실행 시 결과 파일 생성 완료 메시지 출력

2. **사용된 문법 및 라이브러리:**  
   - 표준 라이브러리  
     - `os` → 디렉터리·파일 조작  
     - `datetime`, `timedelta` → 날짜·시간 처리  
     - `zoneinfo.ZoneInfo` → 미국 동부시각(ET) 타임존  
   - 외부 라이브러리  
     - `yaml` → `config.yaml` 로딩  
     - `requests` → HTTP API 호출 및 웹페이지 요청  
     - `bs4.BeautifulSoup` → HTML 파싱  
     - `pandas` → DataFrame 생성·병합·CSV 저장  

3. **주요 함수·메서드 설명:**  
   - `fetch_yahoo_news(symbol: str, count: int) -> pd.DataFrame`  
     1. Yahoo Finance 검색 API 호출 (뉴스 최대 `count`개)  
     2. JSON 응답에서 `providerPublishTime`, `title` 추출  
     3. 타임스탬프 → ET 기준 `YYYY-MM-DD HH:MM:SS ZZZ` 문자열 변환  
     4. `site='Yahoo Finance'`, `title`, `time` 컬럼으로 DataFrame 반환  
   - `fetch_finviz_news(symbol: str, count: int) -> pd.DataFrame`  
     1. Finviz 종목 페이지 요청 → `<table id="news-table">` 찾기  
     2. 각 `<tr>`에서 시간(raw_time)·제목(title) 파싱  
     3. ET 기준 날짜·시간 합쳐 `YYYY-MM-DD HH:MM:SS ZZZ` 문자열 생성  
     4. `site='Finviz'`, `title`, `time` 컬럼으로 DataFrame 반환  
   - `NewsCrawler(symbols: list[str] | None, news_dir: str, config_path: str) -> list[str]`  
     1. `symbols` 미지정 시 `config.yaml` 또는 `DEFAULT_SYMBOLS` 사용  
     2. `news_dir` 초기화(폴더 생성 + 기존 CSV 삭제)  
     3. 각 종목목에 대해  
        - `fetch_yahoo_news` + `fetch_finviz_news` 호출 → DataFrame 병합  
        - `YYYYMMDD_HHMMSS_ET` 타임스탬프 기반 파일명 생성  
        - `site, title, time` 컬럼만 CSV로 저장  
        - 저장 경로를 리스트에 추가  
     4. 생성된 CSV 경로 리스트 반환  

### 🤖 SentimentAnalyzer.py

1. **역할:**  
   - 로컬 `news` 디렉터리 내 CSV 파일을 읽어  
     1. 각 기사 제목에 대해 사전 학습된 Transformer 모델로 감정 예측  
     2. 예측 결과를 포함한 새로운 CSV (`*_sentiment.csv`) 생성  
   - 단일 감정 결과 파일을 종합하여 종목별 점수(-1, 0, +1) 반환

2. **사용된 문법 및 라이브러리:**  
   - 표준 라이브러리  
     - `os`, `glob` → 파일 시스템 탐색 및 처리  
     - `pathlib.Path` → 경로 조작  
     - `zoneinfo.ZoneInfo` → 타임존(ET) 지정  
   - 서드파티 라이브러리  
     - `pandas` → CSV 읽기·쓰기, DataFrame 처리  
     - `transformers.AutoTokenizer`, `transformers.AutoModelForSequenceClassification` → 사전 학습된 NLP 모델 로딩  
     - `torch`, `torch.no_grad()` → 모델 추론  
     - `torch.nn.functional` → Softmax 연산  

3. **주요 함수·메서드 설명:**  
   - `@torch.no_grad() predict_sentiment(text: str) -> int`  
     1. 토크나이저로 입력 텍스트를 텐서화  
     2. 모델에 통과시켜 로짓(logits) 획득  
     3. Softmax 후 argmax로 클래스 인덱스(0: negative, 1: neutral, 2: positive) 반환  
   - `get_sentiment_analysis(data_dir: str = "news", out_dir: str = "sentiment") -> None`  
     1. `data_dir` 내 모든 `*.csv` 파일 목록 조회  
     2. `out_dir` 초기화(디렉터리 생성 + 기존 CSV 삭제)  
     3. 각 CSV별로  
        - 제목 컬럼(`title`) 기반 감정 예측  
        - 원본 컬럼에 `predicted_class`, `label_name` 열 추가  
        - `site, title, time, predicted_class, label_name` 컬럼만 추려 `*_sentiment.csv`로 저장  
   - `SentimentAnalyzer(csv_path: str) -> int`  
     1. 단일 감정 결과 CSV 읽기  
     2. `label_name=="neutral"`인 행 제외 후  
     3. 남은 항목에서  
        - 긍정(`positive`) ≥ 전체의 2/3 → `+1`  
        - 부정(`negative`) ≥ 전체의 2/3 → `-1`  
        - 그 외 → `0` 반환  

### 💱 TradingBot.py

1. **역할:**  
   - 증권사 API와 연동하여  
     - **인증 토큰 관리**  
     - **시세·차트·체결강도 조회**  
     - **계좌·잔고·평가 조회**  
     - **매수·매도 주문 실행**  
     - **Discord 알림** 및 **TradeLogger 연동 로깅**  
   - AutoTrader 등 상위 모듈이 호출할 수 있는 핵심 트레이딩 기능을 제공  

2. **사용된 문법 및 라이브러리:**  
   - 표준 라이브러리  
     - `json`, `os`, `glob`, `pathlib.Path` → 파일 I/O 및 경로 조작  
     - `datetime as dt`, `zoneinfo.ZoneInfo` → 시간·타임존 처리  
     - `typing` → 타입 힌트 (`Any`, `Dict`, `List`, `Optional`)  
   - 외부 라이브러리  
     - `yaml` → `config.yaml` 로드  
     - `requests` → REST API 호출  
     - `TradeLogger` → 거래 내역·스냅샷 로깅  

3. **주요 메서드 설명:**  
   - `__init__(config_path, buy_percent, …)`  
     - `config.yaml` 로 인증 키·계정 정보 로딩  
     - 저장된 토큰(`token.json`) 불러오기  
     - 거래 파라미터(`buy_percent`, `target_buy_count` 등) 초기화  
   - **토큰 관리**  
     - `_load_saved_token()`, `_save_token()` → 로컬 파일에 토큰 저장/복원  
     - `_request_new_token()` → 신규 토큰 발급 → 저장 → Discord 알림  
     - `refresh_token_if_needed()` → 유효시간(18h) 체크 후 재발급  
   - **알림**  
     - `send_message(msg)` → Discord Webhook으로 타임스탬프 포함 알림  
   - **시세 조회**  
     - `get_current_price(market, code)` → REST 호출로 현재가 조회 → 알림  
     - `get_chart_data(market, code, interval, count)` → 분봉 데이터 파싱 → 리스트 반환 → 알림  
     - `get_trade_intensity(market, code, tday)` → 체결강도(시간별 체결량) 조회 → 리스트 반환 → 알림  
   - **계좌·잔고·평가**  
     - `get_balance()` → 국내 현금 잔고 조회 → 알림  
     - `get_stock_balance()` → 해외 보유 종목 조회 → 딕셔너리 반환 → 알림  
     - `get_account_summary()` → 환율·해외 평가금액·손익·총자산 계산 → 알림 → 요약 반환  
   - **주문 실행**  
     - `buy(market, code, qty, price)`  
     - `sell(market, code, qty, price)`  
     - 각 메서드가 트랜잭션 데이터 구성 → 해시키 생성 → 주문 API 호출  
     - 성공 시 Discord 알림 및 `TradeLogger.log_trade` 호출, 실패 시 에러 알림  


### 📈 TradeLogger.py  

1. **역할:**  
   - 자동매매 실행 중 발생하는 **개별 거래(매수·매도)** 내역과 **자산 상태 스냅샷**을  
     CSV 파일로 기록  
   - 기록된 데이터를 바탕으로 **자산 변화**, **현금 vs. 주식 가치**, **실현 P/L**, **개별 거래 규모**를  
     시간 경과에 따라 시각화

2. **사용된 문법 및 라이브러리:**  
   - 표준 라이브러리  
     - `csv`, `datetime as dt` → CSV 입출력, 타임스탬프 생성  
     - `pathlib.Path`, `os` → 디렉터리·파일 생성 및 검사  
     - `zoneinfo.ZoneInfo` → 한국 시간(KST) 지정  
   - 서드파티 라이브러리  
     - `pandas` → `equity.csv`, `trades.csv` 읽기 및 데이터 처리  
     - `matplotlib.pyplot` → 자산 변화 및 거래 규모 그래프 출력  

3. **주요 메서드 설명:**  
   - `__init__(log_dir: str = "logs")`  
     - 로그 디렉터리 생성, `trades.csv`와 `equity.csv` 파일이 없으면 헤더만 작성  
     - `realized_pnl`(실현 손익) 초기화  
   - `log_trade(symbol: str, side: str, qty: float, price: float) -> None`  
     1. 거래 금액(`qty × price`) 계산 (매도는 음수)  
     2. 매도 시 `realized_pnl` 누적  
     3. 현재 KST 타임스탬프로 `[time, symbol, side, qty, price, amount]` 행을 `trades.csv`에 추가  
   - `log_snapshot(cash: float, stock_value: float) -> None`  
     1. `cash + stock_value`로 `total_equity` 계산  
     2. 현재 `realized_pnl` 포함 `[time, cash, stock_value, total_equity, realized_pnl]` 행을 `equity.csv`에 추가  
   - `draw_graphs() -> None`  
     1. `equity.csv` 로드 후 시간 경과(`elapsed_min`) 계산  
     2. **그래프 4종** 그리기:  
        - Total Equity  
        - Cash vs. Stock Value  
        - Cumulative Realized P/L  
        - Individual Trade Amounts (거래별 금액 산점도)  
     3. `plt.show()`로 창에 출력  

### 💱 AutoTrader.py

1. **역할:**  
   - `TradingBot`, `NewsCrawler`, `SentimentAnalyzer`, `TradeLogger` 모듈을 연결하여  
     지정된 종목에 대해  
     1. 뉴스 크롤링 → 감성 분석  
     2. 가격 차트 데이터 조회 → Momentum·RSI 계산  
     3. 매수·매도 판단 → 주문 실행  
     4. 결과 알림 및 로그 기록  
   - 위 과정을 일정 간격(`interval_sec`)으로 반복 실행하는 자동 매매 루프 스크립트

2. **사용된 문법 및 라이브러리:**  
   - **표준 라이브러리**  
     - `threading`, `time` → 멀티스레드·대기 제어  
     - `datetime as dt`, `zoneinfo.ZoneInfo` → 미국 동부시각(ET) 기준 시간 처리  
     - `statistics` → 평균 계산  
     - `yaml` → `config.yaml` 읽기  
     - `typing.List`, `typing.Dict`, `typing.Optional` → 타입 힌트  
   - **서드파티 라이브러리**  
     - `numpy` → 배열 연산 (RSI 계산용)  
   - **내부 모듈**  
     - `TradingBot` → 계좌 조회·매매 API  
     - `NewsCrawler` → 뉴스 크롤링  
     - `SentimentAnalyzer` → 뉴스 감성 점수  
     - `TradeLogger` → 거래·자산 로그 기록

3. **주요 함수·메서드 설명:**  
   - `__init__(*, stop_event, config_path, symbols)`  
     - `config.yaml` 로드 → `TradingBot`, `TradeLogger` 초기화  
     - 사용자 설정(종목, 매수 단위, RSI 기간 등) 속성에 저장  
     - `stop_event`를 통해 외부 중단 신호 수신 준비  
   - `compute_scores(sym, sentiment, price_bars) -> Dict[str,int]`  
     - **Sentiment (S)**, **Momentum (M)**, **RSI (R)** 3요소 계산  
     - 각 항목에 `+1/0/−1` 점수 부여 → `total` 합산  
   - `decide_trade(total, holdings) -> str`  
     - `total ≥ 1` → `"buy"`  
     - `total ≤ -1` & 보유 수량 > 0 → `"sell"`  
     - 그 외 → `"hold"`  
   - `loop_once() -> None`  
     1. 현지 시간(ET) 확인 → 장중/장외·주말 여부 판정  
     2. 비거래 시간엔 대기(`test_mode=False`일 때만)  
     3. `NewsCrawler` → `SentimentAnalyzer` → 종목별 감성 점수 계산  
     4. `TradingBot`로 계좌·환율·보유 조회  
     5. 차트 데이터 조회 → `compute_scores`, `decide_trade`  
     6. 주문 실행(Test/Real) → `TradeLogger.log_trade`  
     7. `TradeLogger.log_snapshot`으로 자산 스냅샷 기록  
     8. 다음 종목 간 최소 1초 대기  
   - `run() -> None`  
     - 시작 시 모드 알림 → `loop_once()` 반복 실행  
     - 예외 발생 시 Discord 알림 → 지정 주기(`interval_sec`) 유지  
     - `stop_event` 신호 수신 시 루프 종료 알림

### 🛠️ main.py  
1. **역할:**  
   - `AutoTrader` 루프를 **데몬 스레드**로 실행·모니터링  
   - **SIGINT(Ctrl+C)** 신호 수신 시 즉시 종료  
   - `AutoTrader`가 예외로 종료되면 30초 후 자동 재시작  
   - 전체 실행 상태를 **Discord**로 알림  

2. **사용된 문법 및 라이브러리:**  
   - 표준 라이브러리  
     - `threading.Event` → 전역 종료 플래그(`STOP_EVENT`)  
     - `signal` → SIGINT 핸들러 등록  
     - `sys.exit` → 메인 스레드 강제 종료  
     - `time.sleep` → 재시작 대기  
     - `datetime as dt`, `zoneinfo.ZoneInfo` → 타임존 처리(ET)  
   - 내부 모듈  
     - `AutoTrader` → 자동 매매 루프 스크립트  
     - `TradingBot` → Discord 메시지 전송용 인스턴스  

3. **주요 함수·메서드 설명:**  
   - `_sigint_handler(sig, frame)`  
     1. Discord에 `"🛑 SIGINT 수신 : 즉시 종료"` 메시지 전송  
     2. `STOP_EVENT.set()` → 실행 중인 `AutoTrader` 스레드에도 종료 신호  
     3. `sys.exit(0)` → 메인 프로세스 즉시 종료  
   - `main()`  
     1. `while not STOP_EVENT.is_set():`  
        - `AutoTrader(stop_event=STOP_EVENT)` 인스턴스 생성  
        - 데몬 스레드로 `trader.run()` 실행  
     2. 스레드가 살아있는 한 1초마다 `join(timeout=1)` 대기  
     3. `STOP_EVENT`가 설정되면 루프 탈출  
     4. `AutoTrader`가 예외로 종료되면  
        - `"❌ AutoTrader 종료 : 30초 후 재시작"` 메시지 전송  
        - `time.sleep(30)` 후 루프 재시작  
     5. 루프 종료 후 `"👋 main.py 정상 종료"` 메시지 전송  


## 📦 2. 사용 방법

1. **Git clone**  
   ```bash
   git clone https://github.com/sjkim-snu/2025_PythonProject.git

2. **Learning Parameters Download**
   - https://drive.google.com/file/d/1h_ABxd10qbEwSp68wu3CrlbYUV67WN5N/view?usp=sharing
   - Clone 폴더 내부에 다운로드 후 압축 해제 


3. **환경 설정 (Anaconda Prompt에서 실행)**  
   ```bash
    conda env create -n my_custom_env -f environment.yml
    conda activate my_custom_env

4. **설정 파일 작성 (`config.yaml`)**  
   ```yaml
   # 한국투자증권에서 API 서비스 신청 시 받은 Appkey, Appsecret 값
   APP_KEY: "your_app_key"                     
   APP_SECRET: "your_app_secret"

   # CANO : 계좌번호 앞 8자리, ACNT : 계좌번호 뒤 2자리  
   CANO: "your_account_number"  
   ACNT_PRDT_CD: "your_product_code"

   # Discord 알림 기능 설정
   DISCORD_WEBHOOK_URL: "your_discord_webhook_url"

   # 한국투자증권 API 홈페이지  
   URL_BASE: "https://api.koreainvestment.com"

   # 투자 설정  
   SYMBOLS:                 # NASDAQ 종목 지정
     - AAPL                 # Apple  
     - MSFT                 # Microsoft
     - AMZN                 # Amazon
   BUY_UNIT_USD: 100        # 최대 매수 금액 (USD)
   MOMENTUM_BARS: 3         # Momentum 계산 시 사용하는 분봉의 개수
   RSI_PERIOD: 14           # RSI 계산 시 사용하는 분봉의 개수
   TEST_MODE: true          # True : 테스트 모드 (매수/매도 제외하고 실행)
   INTERVAL_SEC: 60         # Loop 주기 (매수/매도 주기)
   IDLE_INTERVAL_SEC: 1800  # 대기 모드 알림 주기 (장외시간)

5. **코드 실행**  
   ```bash
   cd 2025_PythonProject
   python main.py

6. **뉴스 데이터, 거래 로그 및 차트 확인**
- 원본 뉴스 CSV: `news/`  
- 감성 분석 CSV: `sentiment/`    
- 트레이드 내역: `logs/trades.csv`  
- 자산 스냅샷: `logs/equity.csv`  
- 성과 그래프 출력:
    ```bash
    python TradeLogger.py
    ```
7. **Reference Code**
- 개발 과정에서 유튜버 조코딩이 개발한 코드를 참조하였음
- https://github.com/youtube-jocoding/koreainvestment-autotrade

## 3. 🤖 About Sentiment Analysis

**Transformer 모델 사용**  
- **Self-Attention**: 입력 시퀀스의 각 토큰이 다른 모든 토큰과의 관계를 동적으로 가중합(attention)으로 계산  
- **Multi-Head Attention**: 여러 개의 병렬 attention 헤드를 사용해 다양한 시각에서 문맥 정보 학습  
- **Positional Encoding**: 순서를 고려하기 위해 각 토큰에 위치 정보를 더해 Transformer에 전달  
- **Encoder-Only 구조**: BERT/FinBERT 계열은 Transformer의 encoder 부분만 사용하여 문장 이해와 특성 추출에 집중  

**Jupyter Notebook 연동**  
- `finbert_transformer_sentiment.ipynb` 
-  위 원리를 활용해 `ProsusAI/finbert` Transformer 모델을 금융 뉴스 헤드라인 감성 분석에 fine-tuning 합니다.

**주요 기능:**  
1. **데이터 로드 & 전처리**  
   - `data/training_data_sentiment.csv`에서 (label, text) 쌍 로드  
   - label → 숫자 매핑 (negative=0, neutral=1, positive=2)  
   - train/validation split (80/20)  

2. **Model Setup**  
   - `ProsusAI/finbert` pretrained Transformer model 불러와 3-class classification head 구성  
   - tokenizer 설정 (`AutoTokenizer.from_pretrained`)  

3. **Hyperparameter Tuning (Optuna)**  
   - learning rate, batch size, num_epochs 등을 10 trials 동안 최적화  
   - F1 score를 objective로 `study.optimize` 실행  

4. **Training & Evaluation**  
   - 최적 hyperparameter로 `Trainer` 초기화 후 전체 데이터로 fine-tuning  
   - validation set에서 F1 score 및 accuracy 계산  
   - `confusion_matrix` heatmap 시각화  

5. **Model 저장 & 배포 준비**  
   - fine-tuned model & tokenizer를 `./saved_model/`에 저장  
   - `saved_model.zip`으로 압축하여 배포용으로 준비  

**코드 출처**  
- Data set: [Sentiment Analysis for Financial News (Kaggle)](https://www.kaggle.com/datasets/ankurzing/sentiment-analysis-for-financial-news)  
- Code : [sentiment-analysis-on-financial-news (Kaggle)](https://www.kaggle.com/code/quangnguynngnht/sentiment-analysis-on-financial-news)  

## 👥 4. Contributor
| 담당     | 이름     | 소속           | 주요 역할                                                   |
| -------- | -------- | -------------- | ----------------------------------------------------------- |
| 팀장     | 김철기   | 대학원생       | 프로젝트 일정 관리, TradingBot 개발 (Token 알고리즘) |
| 개발자   | 김성진   | 항공우주공학과 | Code Structure 담당, NewsCrawler, SentimentAnalyzer, AutoTrader 개발      |
| 개발자   | 차의진   | 윤리교육과     | TradingBot 개발 (매수/매도 알고리즘)             |

