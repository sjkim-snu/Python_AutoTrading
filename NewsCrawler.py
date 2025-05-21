import os
import yaml
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("US/Eastern")
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]


def fetch_yahoo_news(symbol: str, count: int = 30) -> pd.DataFrame:
    """
    Yahoo Finance v1 Search API를 호출해
    site, title, time(ET 기준) 컬럼만 가진 DataFrame 반환
    """
    url = 'https://query1.finance.yahoo.com/v1/finance/search'
    params = {
        'q': symbol,
        'newsCount': count,
        'enableFuzzyQuery': 'false',
        'quotesCount': 0,
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for it in data.get('news', [])[:count]:
        ts     = it.get('providerPublishTime', 0)
        dt_et  = datetime.fromtimestamp(ts, tz=ET)
        time_str = dt_et.strftime('%Y-%m-%d %H:%M:%S %Z')
        rows.append({
            'site':  'Yahoo Finance',
            'title': it.get('title', '').strip(),
            'time':  time_str,
        })
    return pd.DataFrame(rows)


def fetch_finviz_news(symbol: str, count: int = None) -> pd.DataFrame:
    """
    Finviz 뉴스 테이블을 크롤링하여
    site, title, time(ET 기준) 컬럼만 가진 DataFrame 반환
    """
    url     = f'https://finviz.com/quote.ashx?t={symbol}&p=d'
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp    = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    soup    = BeautifulSoup(resp.content, 'html.parser')

    table = soup.find('table', id='news-table')
    rows = []
    current_date = None

    for tr in table.find_all('tr')[:count]:
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        raw_time = tds[0].get_text(strip=True)
        title    = tds[1].find('a').get_text(strip=True)

        # 1) 'May-13-25 10:58PM' 형태
        if '-' in raw_time and raw_time[0].isalpha():
            dt_obj = datetime.strptime(raw_time, '%b-%d-%y %I:%M%p').replace(tzinfo=ET)
            current_date = dt_obj.date()
        # 2) Today / Yesterday 처리
        elif raw_time.startswith('Today '):
            date_part = datetime.now(ET).date()
            t_part    = raw_time.split(' ', 1)[1]
            t_obj     = datetime.strptime(t_part, '%I:%M%p').time()
            dt_obj    = datetime.combine(date_part, t_obj, tzinfo=ET)
        elif raw_time.startswith('Yesterday '):
            date_part = (datetime.now(ET) - timedelta(days=1)).date()
            t_part    = raw_time.split(' ', 1)[1]
            t_obj     = datetime.strptime(t_part, '%I:%M%p').time()
            dt_obj    = datetime.combine(date_part, t_obj, tzinfo=ET)
        # 3) 시간만 있는 경우
        else:
            if current_date is None:
                current_date = datetime.now(ET).date()
            t_obj  = datetime.strptime(raw_time, '%I:%M%p').time()
            dt_obj = datetime.combine(current_date, t_obj, tzinfo=ET)

        time_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z')
        rows.append({
            'site':  'Finviz',
            'title': title,
            'time':  time_str,
        })

    return pd.DataFrame(rows)


def NewsCrawler(
    symbols: list[str] | None = None,
    news_dir: str = 'news',
    config_path: str = 'config.yaml'
) -> list[str]:
    """
    • symbols: 크롤할 심볼 리스트. None일 때 config.yaml의 SYMBOLS 사용
    • news_dir: 뉴스 CSV 저장 폴더
    • config_path: 설정 파일 경로
    • 반환: 생성된 CSV 파일 경로 리스트
    """
    # 1) symbols 결정
    if symbols is None:
        try:
            cfg = yaml.safe_load(open(config_path, encoding='utf-8'))
            symbols = cfg.get('SYMBOLS', DEFAULT_SYMBOLS)
        except Exception:
            symbols = DEFAULT_SYMBOLS

    # 2) news_dir 초기화
    os.makedirs(news_dir, exist_ok=True)
    for fname in os.listdir(news_dir):
        if fname.lower().endswith('.csv'):
            os.remove(os.path.join(news_dir, fname))

    saved_paths: list[str] = []

    # 3) 종목별 크롤링 및 저장
    for sym in symbols:
        df_y = fetch_yahoo_news(sym, 30)
        df_f = fetch_finviz_news(sym)
        df   = pd.concat([df_y, df_f], ignore_index=True)

        now_et   = datetime.now(ET).strftime('%Y%m%d_%H%M%S')
        filename = f'{sym}_news_{now_et}_ET.csv'
        filepath = os.path.join(news_dir, filename)

        df.to_csv(
            filepath,
            index=False,
            columns=['site', 'title', 'time'],
            encoding='utf-8-sig'
        )
        saved_paths.append(filepath)

    return saved_paths


# ─── NewsCrawler.py 단독 실행 테스트 ─────────────────────────────────────
if __name__ == '__main__':
    paths = NewsCrawler(None)
    for p in paths:
        print(f'✅ {p} 생성 완료')
