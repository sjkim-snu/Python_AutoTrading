import os
import glob
from pathlib import Path
from typing import List

import pandas as pd
import torch
from zoneinfo import ZoneInfo
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ─────────────── 설정 ────────────────
MODEL_PATH = "./learning_parameters"
DATA_DIR   = "news"
OUT_DIR    = "sentiment"
BATCH_SIZE = 64
MAX_LENGTH = 128
ET         = ZoneInfo("US/Eastern")

# 디바이스 설정 (GPU 없으면 CPU)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 레이블 매핑
label_map = {0: "negative", 1: "neutral", 2: "positive"}

# ─────────── 모델·토크나이저 로드 ───────────
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, use_fast=True)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.to(DEVICE).eval()
if DEVICE.type == "cuda":
    model.half()  # FP16 모드

@torch.no_grad()
def _predict_batch(texts: List[str]) -> List[int]:
    enc = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH
    ).to(DEVICE)
    logits = model(**enc).logits
    return logits.argmax(dim=-1).cpu().tolist()

def get_sentiment_analysis(
    data_dir: str = DATA_DIR,
    out_dir: str = OUT_DIR,
    batch_size: int = BATCH_SIZE
) -> None:
    """
    data_dir/*.csv → out_dir/*_sentiment.csv 로 배치 감정 분석 수행
    """
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    Path(out_dir).mkdir(exist_ok=True)
    # 이전 결과 파일 삭제
    for f in os.listdir(out_dir):
        if f.lower().endswith(".csv"):
            os.remove(os.path.join(out_dir, f))

    csv_paths = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_paths:
        print(f"⚠️ No CSV files found in {data_dir}")
        return

    for csv_path in csv_paths:
        df = pd.read_csv(csv_path)
        if "title" not in df.columns:
            print(f"⚠️ 'title' column not found in {csv_path}, skipping.")
            continue

        titles = df["title"].fillna("").tolist()
        preds: List[int] = []
        for i in range(0, len(titles), batch_size):
            batch = titles[i : i + batch_size]
            preds.extend(_predict_batch(batch))

        df["predicted_class"] = preds
        df["label_name"]      = df["predicted_class"].map(label_map)

        out_file = Path(out_dir) / f"{Path(csv_path).stem}_sentiment.csv"
        cols = [c for c in ["site", "title", "time", "predicted_class", "label_name"] if c in df.columns]
        df.to_csv(out_file, index=False, columns=cols, encoding="utf-8-sig")

        print(f"✅ Processed {Path(csv_path).name} → {out_file.name} ({len(df)} rows)")

def SentimentAnalyzer(csv_path: str) -> int:
    """
    (원래 이름 유지) 단일 CSV 파일을 읽어 neutral 제외 후
    2/3 이상 positive면 +1, 2/3 이상 negative면 -1, 그 외 0 반환
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    if "title" not in df.columns or df.empty:
        return 0

    titles = df["title"].fillna("").tolist()
    preds = []
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i : i + BATCH_SIZE]
        preds.extend(_predict_batch(batch))

    filtered = [p for p in preds if p != 1]
    if not filtered:
        return 0

    total = len(filtered)
    pos = sum(1 for p in filtered if p == 2)
    neg = sum(1 for p in filtered if p == 0)

    if pos >= (2/3) * total:
        return 1
    if neg >= (2/3) * total:
        return -1
    return 0

if __name__ == "__main__":
    try:
        get_sentiment_analysis()
        for f in glob.glob(os.path.join(OUT_DIR, "*_sentiment.csv")):
            score = SentimentAnalyzer(f)
            print(f"🔍 {Path(f).name} sentiment score: {score}")
    except Exception as e:
        print(f"Error: {e}")
