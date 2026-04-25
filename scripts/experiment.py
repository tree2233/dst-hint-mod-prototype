"""
실험: One-hot vs SBERT vs SBERT+Context 힌트 추천 비교

Part 1 — 단일 state 비교 (Case A~D)
Part 2 — 시퀀스 기반 Context Engine 효과 검증 (Seq 1~2)
"""
import json
import sys
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent.parent))
from game_state import GameState
from context_engine import ContextEngine

HINTS_FILE = Path(__file__).parent.parent / "data" / "hints.json"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"  # 한국어 지원


# ── 힌트 로드 ─────────────────────────────────────────────────────────────────

def load_hints():
    with open(HINTS_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── GameState → 자연어 (SBERT 쿼리용) ────────────────────────────────────────

def to_text(s: GameState) -> str:
    parts = []
    if s.health_level == "critical": parts.append("체력이 위험하게 낮다")
    elif s.health_level == "low":    parts.append("체력이 낮다")

    if s.sanity_level == "critical": parts.append("정신력이 위험하게 낮다")
    elif s.sanity_level == "low":    parts.append("정신력이 낮다")

    if s.hunger_level == "critical": parts.append("배고픔이 위험하게 낮다")
    elif s.hunger_level == "low":    parts.append("배고픔이 낮다")

    if s.has_spider_drops:           parts.append("거미와 싸워 괴물고기나 거미 아이템을 보유 중이다")

    # 과학 기계/방어구 정보는 전투·체력·인벤토리 문제가 있을 때만 포함
    # (연관 없는 상황에서 불필요한 노이즈가 되지 않도록)
    combat = s.has_spider_drops or s.health_level in ("low", "critical")
    if not s.science_unlocked and (combat or s.inventory_full):
        parts.append("과학 기계를 아직 만들지 않았다")
    elif s.science_unlocked and (combat or s.inventory_full):
        parts.append("과학 기계를 해금했다")
    if not s.has_armor and (combat or s.day >= 11):
        parts.append("방어구가 없다")

    if s.grass_low and s.twigs_low:  parts.append("풀과 잔가지가 부족하다")
    if s.time_of_day == "dusk":      parts.append("황혼이 다가오고 있다")
    elif s.time_of_day == "night":   parts.append("밤이다")
    if s.inventory_full:             parts.append("인벤토리가 가득 찼다")
    if s.has_gold:                   parts.append("금덩어리를 가지고 있다")
    if s.has_chester:                parts.append("Chester의 눈알 뼈를 가지고 있다")
    if s.in_cave:                    parts.append("동굴 안에 있다")
    if s.day >= 11:                  parts.append("11일 이상 생존했다")
    return ". ".join(parts) + "."


# ── One-hot 인코더 ────────────────────────────────────────────────────────────

VOCAB = {
    "sanity_level":     ["critical", "low", "ok"],
    "health_level":     ["critical", "low", "ok"],
    "hunger_level":     ["critical", "low", "ok"],
    "science_unlocked": ["yes", "no"],
    "has_armor":        ["yes", "no"],
    "has_spider_drops": ["yes", "no"],
    "grass_low":        ["yes", "no"],
    "twigs_low":        ["yes", "no"],
    "has_gold":         ["yes", "no"],
    "has_chester":      ["yes", "no"],
    "inventory_full":   ["yes", "no"],
    "in_cave":          ["yes", "no"],
    "time_of_day":      ["day", "dusk", "night"],
    "day_bucket":       ["1-5", "6-10", "11-15"],
}


def _yn(b: bool) -> str:
    return "yes" if b else "no"


def _one_hot(options, value):
    v = np.zeros(len(options), dtype=np.float32)
    if value in options:
        v[options.index(value)] = 1.0
    return v


def _multi_hot(options, values):
    v = np.zeros(len(options), dtype=np.float32)
    vals = values if isinstance(values, list) else [values]
    if "any" in vals:
        v[:] = 1.0
    else:
        for val in vals:
            if val in options:
                v[options.index(val)] = 1.0
    return v


def encode_state_onehot(s: GameState) -> np.ndarray:
    return np.concatenate([
        _one_hot(VOCAB["sanity_level"],     s.sanity_level),
        _one_hot(VOCAB["health_level"],     s.health_level),
        _one_hot(VOCAB["hunger_level"],     s.hunger_level),
        _one_hot(VOCAB["science_unlocked"], _yn(s.science_unlocked)),
        _one_hot(VOCAB["has_armor"],        _yn(s.has_armor)),
        _one_hot(VOCAB["has_spider_drops"], _yn(s.has_spider_drops)),
        _one_hot(VOCAB["grass_low"],        _yn(s.grass_low)),
        _one_hot(VOCAB["twigs_low"],        _yn(s.twigs_low)),
        _one_hot(VOCAB["has_gold"],         _yn(s.has_gold)),
        _one_hot(VOCAB["has_chester"],      _yn(s.has_chester)),
        _one_hot(VOCAB["inventory_full"],   _yn(s.inventory_full)),
        _one_hot(VOCAB["in_cave"],          _yn(s.in_cave)),
        _one_hot(VOCAB["time_of_day"],      s.time_of_day),
        _one_hot(VOCAB["day_bucket"],       s.day_bucket),
    ])


def encode_hint_onehot(tags: dict) -> np.ndarray:
    return np.concatenate([
        _multi_hot(VOCAB["sanity_level"],     tags.get("sanity_level",     "any")),
        _multi_hot(VOCAB["health_level"],     tags.get("health_level",     "any")),
        _multi_hot(VOCAB["hunger_level"],     tags.get("hunger_level",     "any")),
        _multi_hot(VOCAB["science_unlocked"], tags.get("science_unlocked", "any")),
        _multi_hot(VOCAB["has_armor"],        tags.get("has_armor",        "any")),
        _multi_hot(VOCAB["has_spider_drops"], tags.get("has_spider_drops", "any")),
        _multi_hot(VOCAB["grass_low"],        tags.get("grass_low",        "any")),
        _multi_hot(VOCAB["twigs_low"],        tags.get("twigs_low",        "any")),
        _multi_hot(VOCAB["has_gold"],         tags.get("has_gold",         "any")),
        _multi_hot(VOCAB["has_chester"],      tags.get("has_chester",      "any")),
        _multi_hot(VOCAB["inventory_full"],   tags.get("inventory_full",   "any")),
        _multi_hot(VOCAB["in_cave"],          tags.get("in_cave",          "any")),
        _multi_hot(VOCAB["time_of_day"],      tags.get("time_of_day",      "any")),
        _multi_hot(VOCAB["day_bucket"],       tags.get("day_bucket",       "any")),
    ])


# ── 추천 함수 ─────────────────────────────────────────────────────────────────

def recommend_onehot(state: GameState, hints: list, top_k=3):
    query  = encode_state_onehot(state).reshape(1, -1)
    vecs   = np.array([encode_hint_onehot(h["tags"]) for h in hints])
    scores = cosine_similarity(query, vecs)[0]
    idx    = scores.argsort()[::-1][:top_k]
    return [(hints[i]["id"], float(scores[i]), hints[i]["text"]) for i in idx]


def recommend_sbert(state: GameState, hints: list, model, hint_embs, top_k=3):
    query_text = to_text(state)
    query_emb  = model.encode([query_text])
    scores     = cosine_similarity(query_emb, hint_embs)[0]
    idx        = scores.argsort()[::-1][:top_k]
    return [(hints[i]["id"], float(scores[i]), hints[i]["text"]) for i in idx]


def recommend_sbert_ctx(
    state: GameState, hints: list, model, hint_embs,
    ctx: ContextEngine, top_k=3,
) -> list:
    """Context Engine이 적용된 SBERT 추천. push_state/push_shown은 호출자가 관리."""
    query_text = to_text(state)
    q_emb      = model.encode([query_text])[0]
    q_adj      = ctx.adjust_query(q_emb)
    scores     = cosine_similarity(q_adj.reshape(1, -1), hint_embs)[0]
    hint_ids   = [h["id"] for h in hints]
    scores     = ctx.apply_score_penalty(scores, hint_ids)
    idx        = scores.argsort()[::-1][:top_k]
    return [(hints[i]["id"], float(scores[i]), hints[i]["text"]) for i in idx]


# ── 출력 ──────────────────────────────────────────────────────────────────────

def print_comparison(label: str, desc: str, state: GameState,
                     onehot_results, sbert_results):
    W = 70
    print(f"\n{'='*W}")
    print(f"  {label}")
    print(f"  상태: {desc}")
    print(f"  쿼리: {to_text(state)}")
    print(f"{'-'*W}")
    print(f"  {'[One-hot]':<35}  {'[SBERT]'}")
    print(f"{'-'*W}")
    for i in range(3):
        o_id, o_sc, o_tx = onehot_results[i]
        s_id, s_sc, s_tx = sbert_results[i]
        o_str = f"{i+1}. {o_id} ({o_sc:.2f}) {o_tx[:22]}..."
        s_str = f"{i+1}. {s_id} ({s_sc:.2f}) {s_tx[:22]}..."
        print(f"  {o_str:<35}  {s_str}")
    print(f"{'='*W}")


# ── 테스트 데이터 ─────────────────────────────────────────────────────────────

def make_state(**kwargs) -> GameState:
    defaults = dict(
        health_level="ok", sanity_level="ok", hunger_level="ok",
        science_unlocked=False, has_armor=False,
        has_spider_drops=False, grass_low=False, twigs_low=False,
        has_gold=False, has_chester=False,
        inventory_full=False, in_cave=False,
        time_of_day="day", day=3, day_bucket="1-5",
    )
    defaults.update(kwargs)
    return GameState(**defaults)


TEST_CASES = [
    # ── 완전 일치: 둘 다 h01을 1위로 선택해야 함 ──────────────────────────────
    (
        "Case A │ 완전 일치 — 정신력 위기",
        "sanity=critical, 기타 수치 정상 → h01(꽃 채취)이 명확한 정답",
        make_state(sanity_level="critical"),
    ),
    # ── 태그 완전 일치: one-hot이 구조적 제약(science=no)을 명확히 구별 ──────────
    # One-hot: spider+health+science=no 조건이 h02에 완전 일치 → h02 1위
    # SBERT  : "방어구가 없다" 텍스트 때문에 armor 힌트(h03)를 더 높게 평가
    #          → 구조적 제약(science=no이면 h03은 불가)을 의미론적으로 놓침
    (
        "Case B │ one-hot 우위 — 구조 제약 이해",
        "spider=yes, health=low, science=no → h02가 정답 (h03는 science=yes 필요)",
        make_state(health_level="low", has_spider_drops=True, science_unlocked=False),
    ),
    # ── One-hot 구조적 편향: 태그 wildcard가 많은 h05가 점수 과대평가됨 ──────────
    # One-hot: spider_drops 불일치로 h02 점수 하락, wildcard가 많은 h05(day11 경고)가 1위
    #          → 실제로 day=3인 플레이어에게 완전히 무관한 힌트
    # SBERT  : "체력 낮음" 텍스트로 전투/체력 관련 h03, h02를 선택 → 더 관련성 높음
    (
        "Case C │ SBERT 우위 — wildcard 편향 vs 의미 기반 선택",
        "health=low, science=no, spider=NO → h02 태그 불일치, one-hot은 무관한 h05 선택",
        make_state(health_level="low", science_unlocked=False,
                   has_spider_drops=False),
    ),
    # ── 완전 일치 없음: one-hot wildcard 편향, SBERT는 인벤토리 텍스트로 찾음 ────
    # One-hot: 모든 인벤 힌트(h08/h09/h10)에 태그 불일치 존재
    #          → wildcard가 많은 h05(day11 경고)가 또 1위 (완전히 무관)
    # SBERT  : "인벤토리가 가득 찼다. 과학 기계를 아직 만들지 않았다" 쿼리로
    #          h08(인벤 + 과학 기계 해법)을 정확히 선택
    (
        "Case D │ SBERT 우위 — 태그 불일치 상황에서 의미론적 검색",
        "inv_full=yes, science=no, gold=NO, chester=NO → 완전 일치 힌트 없음",
        make_state(inventory_full=True, science_unlocked=False,
                   has_gold=False, has_chester=False),
    ),
]


# ── 시퀀스 테스트 케이스 ──────────────────────────────────────────────────────
# 각 케이스: (레이블, [(state, 이 state에서 어떤 힌트를 제시했는지 표시 이름)])
SEQUENCE_CASES = [
    (
        "Seq 1 │ Anti-repetition — day 11 하운드 경고 반복 억제",
        "h05가 t=0에 이미 제시됐을 때, t=1에서 억제되는지 확인",
        [
            make_state(day=11, day_bucket="11-15", has_armor=False, time_of_day="day"),
            make_state(day=11, day_bucket="11-15", has_armor=False, time_of_day="day"),
        ],
    ),
    (
        "Seq 2 │ Delta embedding — 정신력 ok → critical 악화",
        "delta가 h01 방향으로 쿼리를 강화하는지 확인 (점수 상승 여부)",
        [
            make_state(sanity_level="ok"),
            make_state(sanity_level="critical"),
        ],
    ),
]


def run_sequence(label, desc, states, hints, model, hint_embs, ctx: ContextEngine):
    W = 74
    print(f"\n{'═'*W}")
    print(f"  {label}")
    print(f"  {desc}")
    print(f"  Context: {ctx.status()}")
    print(f"{'─'*W}")
    header = f"  {'t':<3}  {'[SBERT 기준]':<34}  {'[SBERT+Context]':<34}  변화"
    print(header)
    print(f"{'─'*W}")

    hint_ids = [h["id"] for h in hints]

    for t, state in enumerate(states):
        # 기준 SBERT (context 없음)
        sb_base = recommend_sbert(state, hints, model, hint_embs, top_k=1)

        # context 기반 (push_state → adjust → score penalty)
        q_text = to_text(state)
        q_emb  = model.encode([q_text])[0]
        ctx.push_state(q_emb)
        sb_ctx = recommend_sbert_ctx(state, hints, model, hint_embs, ctx, top_k=1)

        # 이번 turn에 제시할 힌트 기록 (context 기반 결과 기준)
        top_id = sb_ctx[0][0]
        top_idx = hint_ids.index(top_id)
        ctx.push_shown(top_id, hint_embs[top_idx])

        b_id, b_sc, b_tx = sb_base[0]
        c_id, c_sc, c_tx = sb_ctx[0]
        b_str = f"{b_id} ({b_sc:.2f}) {b_tx[:22]}..."
        c_str = f"{c_id} ({c_sc:.2f}) {c_tx[:22]}..."

        changed = ""
        if b_id != c_id:
            changed = f"← {b_id} 억제됨" if t > 0 else ""
        elif abs(b_sc - c_sc) > 0.005:
            diff = c_sc - b_sc
            changed = f"점수 {'↑' if diff > 0 else '↓'}{abs(diff):.3f}"

        print(f"  t={t}  {b_str:<34}  {c_str:<34}  {changed}")

    print(f"{'═'*W}")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    hints = load_hints()

    print("SBERT 모델 로딩 중...")
    model     = SentenceTransformer(MODEL_NAME)
    hint_embs = model.encode([h["text"] for h in hints], show_progress_bar=False)
    print(f"힌트 {len(hints)}개 인코딩 완료.\n")

    # ── Part 1: 단일 state 비교 ───────────────────────────────────────────────
    print("━" * 74)
    print("  Part 1. One-hot vs SBERT (단일 state)")
    print("━" * 74)
    for label, desc, state in TEST_CASES:
        oh = recommend_onehot(state, hints)
        sb = recommend_sbert(state, hints, model, hint_embs)
        print_comparison(label, desc, state, oh, sb)

    # ── Part 2: Context Engine 시퀀스 테스트 ─────────────────────────────────
    print("\n\n")
    print("━" * 74)
    print("  Part 2. SBERT vs SBERT+Context (시퀀스 기반)")
    print("  Context Engine 설정: interval=30s → delta+centroid+anti-repeat 활성")
    print("━" * 74)
    for label, desc, states in SEQUENCE_CASES:
        ctx = ContextEngine(load_interval_sec=30)
        run_sequence(label, desc, states, hints, model, hint_embs, ctx)


if __name__ == "__main__":
    main()
