import os, glob
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

# ─────────────── 설정 ────────────────
ET = ZoneInfo('US/Eastern')
MODEL_PATH = "./learning_parameters"
# ─────────────────────────────────────

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
label_map = {0: "negative", 1: "neutral", 2: "positive"}

@torch.no_grad()
def predict_sentiment(text: str) -> int:
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    logits = model(**inputs).logits
    pred = int(logits.softmax(dim=1).argmax(dim=1).item())
    return pred


def get_sentiment_analysis(data_dir: str = "news", out_dir: str = "sentiment") -> None:
    """
    data_dir/*.csv → out_dir/*_sentiment.csv 으로 감정 결과 저장
    """
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    # 결과 디렉터리 초기화
    Path(out_dir).mkdir(exist_ok=True)
    for fname in os.listdir(out_dir):
        if fname.lower().endswith('.csv'):
            os.remove(os.path.join(out_dir, fname))

    csv_paths = glob.glob(os.path.join(data_dir, '*.csv'))
    if not csv_paths:
        print(f"⚠️ No CSV files found in {data_dir}")
        return

    for csv_path in csv_paths:
        df = pd.read_csv(csv_path)
        if 'title' not in df.columns:
            print(f"⚠️ 'title' column not found in {csv_path}, skipping.")
            continue

        # 감정 예측
        df['predicted_class'] = df['title'].apply(predict_sentiment)
        df['label_name'] = df['predicted_class'].map(label_map)

        # 저장
        base = Path(csv_path).stem
        out_file = Path(out_dir) / f"{base}_sentiment.csv"
        wanted = ['site', 'title', 'time', 'predicted_class', 'label_name']
        cols = [c for c in wanted if c in df.columns]
        df.to_csv(out_file, index=False, columns=cols, encoding='utf-8-sig')

        print(f"✅ Processed {base}.csv → {out_file.name} ({len(df)} rows)")


def SentimentAnalyzer(csv_path: str) -> int:
    """
    단일 CSV 파일의 제목별 감정을 예측하여 종합 점수(-1, 0, +1)로 반환
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    df = pd.read_csv(csv_path)
    if 'title' not in df.columns or df.empty:
        return 0

    # neutral 제외하고 집계
    preds = df['title'].apply(predict_sentiment)
    filtered = preds[preds != 1]
    if filtered.empty:
        return 0

    total = len(filtered)
    pos = (filtered == 2).sum()
    neg = (filtered == 0).sum()

    if pos >= (2/3) * total:
        return 1
    if neg >= (2/3) * total:
        return -1
    return 0


if __name__ == "__main__":
    try:
        get_sentiment_analysis()
        # sentiment 폴더의 결과 파일만 다시 평가
        sentiment_files = glob.glob(os.path.join('sentiment', '*_sentiment.csv'))
        for f in sentiment_files:
            score = SentimentAnalyzer(f)
            print(f"🔍 {Path(f).name} sentiment score: {score}")
    except Exception as e:
        print(f"Error: {e}")
