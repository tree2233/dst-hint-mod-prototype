"""
terminal_hint.py — 실제 게임 client.log를 실시간으로 읽어 터미널에 힌트 출력.

실행:
    python3 scripts/terminal_hint.py
    python3 scripts/terminal_hint.py --interval 30   # mod 기록 주기 지정 (초)

게임 state가 바뀔 때마다 One-hot / SBERT / SBERT+Context 세 결과를 비교 출력.
Context Engine(interval=30s 기준): delta + centroid + anti-repeat 전부 활성.
"""
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))   # dst-hint-system/
sys.path.insert(0, str(Path(__file__).parent))           # scripts/

from read_mod_state import load_state, LOG_PATH
from experiment import (
    load_hints, recommend_onehot, recommend_sbert, recommend_sbert_ctx, to_text,
)
from context_engine import ContextEngine
from sentence_transformers import SentenceTransformer

MODEL_NAME   = "paraphrase-multilingual-MiniLM-L12-v2"
POLL_SEC     = 5.0    # 로그 파일 확인 주기 (초)
W            = 72     # 출력 너비


def fmt(hint_id, score, text, max_len=52):
    snippet = text[:max_len] + ("..." if len(text) > max_len else "")
    return f"{hint_id} ({score:.2f})  {snippet}"


def print_hint(state, oh, sb, sb_ctx, ctx):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'═'*W}")
    print(
        f"  [{now}]  Day {state.day}  {state.time_of_day.upper()}  │  "
        f"HP:{state.health_level}  SAN:{state.sanity_level}  HUN:{state.hunger_level}"
    )
    print(f"  쿼리: {to_text(state)}")
    print(f"{'─'*W}")
    print(f"  One-hot        {fmt(*oh[0])}")
    print(f"  SBERT          {fmt(*sb[0])}")
    print(f"  SBERT+Context  {fmt(*sb_ctx[0])}")
    if sb[0][0] != sb_ctx[0][0]:
        print(f"  ※ Context 효과: {sb[0][0]} → {sb_ctx[0][0]}")
    print(f"  [ctx] {ctx.status()}")
    print(f"{'═'*W}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=30.0,
                        help="mod 기록 주기 추정치(초). 기본값 30.")
    args = parser.parse_args()

    print("SBERT 모델 로딩 중...")
    hints     = load_hints()
    model     = SentenceTransformer(MODEL_NAME)
    hint_embs = model.encode([h["text"] for h in hints], show_progress_bar=False)
    hint_ids  = [h["id"] for h in hints]

    ctx = ContextEngine(load_interval_sec=args.interval)
    print(f"힌트 {len(hints)}개 인코딩 완료.")
    print(f"로그 감시: {LOG_PATH}")
    print(f"Context: {ctx.status()}")
    print(f"(state 변화 감지 시 자동 출력 / Ctrl+C로 종료)\n")

    prev_state = None

    while True:
        state = load_state(LOG_PATH)

        if state is not None and state != prev_state:
            # 기준 추천
            oh = recommend_onehot(state, hints, top_k=1)
            sb = recommend_sbert(state, hints, model, hint_embs, top_k=1)

            # Context 추천 (push_state 내부 처리)
            q_emb = model.encode([to_text(state)])[0]
            ctx.push_state(q_emb)
            sb_ctx = recommend_sbert_ctx(state, hints, model, hint_embs, ctx, top_k=1)

            print_hint(state, oh, sb, sb_ctx, ctx)

            # 제시된 힌트 기록 (context 기반 결과)
            top_id  = sb_ctx[0][0]
            top_idx = hint_ids.index(top_id)
            ctx.push_shown(top_id, hint_embs[top_idx])

            prev_state = state

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료.")
