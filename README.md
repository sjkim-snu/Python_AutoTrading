# 🚀 2025 Python Project

## 📖 Table of Contents
1. 🛠️ 코드 설명 및 구조  
2. 📦 사용 방법
3. 🤖 About Sentiment Analysis
4. 👥 Contributor  

## 🛠️ 1. 코드 설명 및 구조

### 🧭 AutoTrader.py  
**역할:** 뉴스 크롤링, 감성 분석, 매매 코드를 통합하여 자동 매매 루프를 실행하는 메인 코드  

**사용된 문법 및 라이브러리:**  
- `config.yaml` 로 설정 로딩  
- `threading`, `time` 을 이용한 루프 제어  
- `TradingBot`, `NewsCrawler`, `SentimentAnalyzer`, `TradeLogger` 클래스 호출  
- ET 타임존 처리: `zoneinfo` 모듈  
**주요 기능:**  
- 종목 별 뉴스 CSV 생성(`news/`)  
- 뉴스 감성 분석 CSV 생성(`sentiment/`)  
- 계좌 정보 및 가격 차트(bar) 데이터 조회  
- Momentum, RSI, 뉴스 지표 계산 후 매수/매도 여부 결정  
- 매수/매도 주문 실행, Discord 알림 발송  
- 로그를 자동으로 기록하여 매매 알고리즘의 성능을 그래프로 확인 가능 (`logs/trades.csv`, `logs/equity.csv`)  

### 📈 TradeLogger.py  
**역할:** 트레이드 및 자산의 Snapshot을 CSV로 기록하고 성과 그래프 출력  

**사용된 문법 및 라이브러리:**  
- `csv`, `pandas` 로 데이터 입출력  
- `matplotlib` 으로 그래프 도출  
**주요 기능:**  
- `logs/trades.csv`, `logs/equity.csv` 초기화 및 헤더 설정  
- `log_trade()`: 실행된 매수/매도 내역 기록  
- `log_snapshot()`: 현금, 주식 평가액, 총자산, 실현 손익 기록  
- `draw_graphs()`: 저장된 CSV 로딩 후 자산 곡선, 현금·주식 비교, 실현 손익, 개별 트레이드 금액 플롯  

### 📰 NewsCrawler.py  
**역할:** 각 종목의 최신 뉴스 크롤링 후 `news/` 폴더에 CSV 저장  

**사용된 문법 및 라이브러리:**  
- `requests`, `BeautifulSoup` 으로 HTTP 요청 및 HTML 파싱  
- `pandas` 로 DataFrame 처리 및 CSV 저장  
- `yaml` 로 `config.yaml` 읽기  
**주요 기능:**  
- `fetch_yahoo_news()`: Yahoo Finance API 이용 뉴스 조회  
- `fetch_finviz_news()`: Finviz 뉴스 테이블 스크래핑 및 시간 정규화  
- 각 종목에 대해 `news/SYM_news_<timestamp>_ET.csv` 파일 생성  

### 🤖 SentimentAnalyzer.py  
**역할:** 저장된 뉴스 CSV 를 바탕으로 헤드라인 감성 분석 및 집계 점수 반환  

**사용된 문법 및 라이브러리:**  
- `transformers`, `torch` 로 사전 학습된 분류 모델 로드 및 추론  
- `pandas` 로 CSV 처리  
**주요 기능:**  
- `get_sentiment_analysis()`: `news/*.csv` → `sentiment/*_sentiment.csv` 생성  
- 중립(neutral) 제외 후, 긍정·부정 비율 2/3 기준으로 점수 (+1, –1, 0) 반환  

### 💱 TradingBot.py  
**역할:** 한국투자증권 API 래퍼로 토큰 관리, 시세·계좌 조회, 주문 실행 기능 제공  

**사용된 문법 및 라이브러리:**  
- `requests`, `yaml` 로 HTTP 요청 및 설정 로딩  
- `hashlib`, `json` 등 해시·직렬화 처리  
**주요 기능:**  
- `_request_new_token()`, `refresh_token_if_needed()`: 토큰 발급 및 갱신, `token.json` 저장  
- `get_balance()`, `get_stock_balance()`, `get_account_summary()`: 잔고 및 환율 포함 요약 조회  
- `get_chart_data()`, `get_trade_intensity()`: 가격 차트(bar) 및 체결 강도 데이터 반환  
- `buy()`, `sell()`: 지정가 주문 실행 및 Discord 알림 전송  

### 🛠️ main.py  
**역할:** `AutoTrader`를 Daemon Thread로 실행하여 오류가 발생해도 코드의 연속적인 실행을 보장, SIGINT Signal (Ctrl + C)로 종료하도록 설정  

**사용된 문법 및 라이브러리:**  
- `threading`, `signal` 로 스레드 및 종료 이벤트 처리  
- ET 타임존 설정: `zoneinfo` 모듈  
**주요 기능:**  
- 전역 `STOP_EVENT` 및 SIGINT 핸들러 설정  
- `AutoTrader.run()` 스레드 실행, 예외 시 30초 대기 후 재시작  


## 📦 2. 사용 방법

1. **Git clone**  
   ```bash
   git clone https://github.com/sjkim-snu/2025_PythonProject.git

2. **환경 설정 (Anaconda Prompt에서 실행)**  
   ```bash
    conda env create -n my_custom_env -f environment.yml
    conda activate my_custom_env

3. **설정 파일 작성 (`config.yaml`)**  
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

4. **코드 실행**  
   ```bash
   cd 2025_PythonProject
   python main.py

5. **뉴스 데이터, 거래 로그 및 차트 확인**
- 원본 뉴스 CSV: `news/`  
- 감성 분석 CSV: `sentiment/`    
- 트레이드 내역: `logs/trades.csv`  
- 자산 스냅샷: `logs/equity.csv`  
- 성과 그래프 출력:
    ```bash
    python TradeLogger.py
    ```
6. **Reference Code**
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
  위 원리를 활용해 `ProsusAI/finbert` Transformer 모델을 금융 뉴스 헤드라인 감성 분석에 fine-tuning 합니다.

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

