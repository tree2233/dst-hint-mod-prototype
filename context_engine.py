"""
context_engine.py — 맥락 기반 SBERT 쿼리 보정 모듈.

세 가지 보정을 조합:
  1. Delta embedding   : 직전 state → 현재 state 변화량을 쿼리에 더함 (상황 악화 강조)
  2. Decaying centroid : 최근 N개 state의 지수 감쇠 무게중심을 쿼리에 더함 (흐름 반영)
  3. Anti-repetition   : 이미 제시된 힌트 방향으로 쿼리를 밀어냄 + 점수 직접 감쇠

load_interval_sec 에 따라 활성화 범위가 달라짐:
  < 10s  : anti-repeat만 사용 (짧은 주기에서 delta/centroid는 노이즈)
  10~60s : delta + centroid + anti-repeat 전부 사용
  > 60s  : centroid + anti-repeat (delta는 변화량이 너무 커서 제외)
"""
import numpy as np
import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class _StateRec:
    emb: np.ndarray
    ts: float = field(default_factory=time.time)


@dataclass
class _HintRec:
    hint_id: str
    emb: np.ndarray
    ts: float = field(default_factory=time.time)


class ContextEngine:
    def __init__(
        self,
        load_interval_sec: float = 30.0,  # mod 기록 주기 추정치
        history_window: int = 5,           # 유지할 최대 state 수
        lambda_delta: float = 0.30,        # 변화량 가중치
        lambda_centroid: float = 0.20,     # 무게중심 가중치
        decay_rate: float = 0.65,          # 지수 감쇠율 (0<x<1, 클수록 최근 편향)
        anti_repeat_penalty: float = 0.50, # 반복 힌트 점수 감쇠 비율
        repeat_window: int = 3,            # 억제 대상 최근 힌트 수
    ):
        self.interval  = load_interval_sec
        self.win       = history_window
        self.lam_d     = lambda_delta
        self.lam_c     = lambda_centroid
        self.decay     = decay_rate
        self.penalty   = anti_repeat_penalty
        self.rep_win   = repeat_window

        self._states: List[_StateRec] = []
        self._shown:  List[_HintRec]  = []

        # 활성화 플래그 (interval 기반)
        self.use_delta    = (10 <= load_interval_sec <= 60)
        self.use_centroid = (load_interval_sec >= 10)

    # ── 등록 ─────────────────────────────────────────────────────────────────

    def push_state(self, emb: np.ndarray) -> None:
        """현재 state 임베딩을 히스토리에 추가."""
        self._states.append(_StateRec(emb.copy()))
        if len(self._states) > self.win:
            self._states.pop(0)

    def push_shown(self, hint_id: str, hint_emb: np.ndarray) -> None:
        """실제로 플레이어에게 제시된 힌트를 기록."""
        self._shown.append(_HintRec(hint_id, hint_emb.copy()))
        if len(self._shown) > self.rep_win:
            self._shown.pop(0)

    # ── 쿼리 보정 ─────────────────────────────────────────────────────────────

    def adjust_query(self, q: np.ndarray) -> np.ndarray:
        """
        현재 state 임베딩 q를 맥락 기반으로 보정한 새 벡터를 반환.
        원본 q는 변경하지 않음.
        """
        q_adj = q.copy()

        # 1. Delta embedding
        if self.use_delta and len(self._states) >= 2:
            delta = q - self._states[-2].emb
            q_adj = q_adj + self.lam_d * delta

        # 2. Decaying centroid
        if self.use_centroid and len(self._states) >= 2:
            embs    = [r.emb for r in self._states]
            weights = [self.decay ** i for i in range(len(embs) - 1, -1, -1)]
            wsum    = sum(weights)
            centroid = sum(w * e for w, e in zip(weights, embs)) / wsum
            q_adj   = q_adj + self.lam_c * centroid

        # 3. Rocchio anti-repetition (embedding 공간에서 이미 제시 힌트 방향 반발)
        if self._shown:
            embs    = [r.emb for r in self._shown]
            weights = [self.decay ** i for i in range(len(embs) - 1, -1, -1)]
            wsum    = sum(weights)
            neg_vec = sum(w * e for w, e in zip(weights, embs)) / wsum
            q_adj   = q_adj - self.penalty * neg_vec

        norm = np.linalg.norm(q_adj)
        return q_adj / norm if norm > 0 else q_adj

    def apply_score_penalty(
        self, scores: np.ndarray, hint_ids: List[str]
    ) -> np.ndarray:
        """
        최근 제시된 힌트의 점수를 직접 감쇠.
        adjust_query()와 병용하면 반복 억제 효과가 강화됨.
        """
        adj = scores.copy()
        shown_ids = {r.hint_id for r in self._shown}
        for i, hid in enumerate(hint_ids):
            if hid in shown_ids:
                adj[i] *= (1.0 - self.penalty)
        return adj

    # ── 상태 조회 ─────────────────────────────────────────────────────────────

    @property
    def ready(self) -> bool:
        """맥락 보정이 가능한 상태(히스토리 2개 이상)인지 여부."""
        return len(self._states) >= 2

    def status(self) -> str:
        modes = []
        if self.use_delta:    modes.append("delta")
        if self.use_centroid: modes.append("centroid")
        modes.append("anti-repeat")
        return (
            f"interval={self.interval}s  "
            f"active=[{', '.join(modes)}]  "
            f"history={len(self._states)}/{self.win}  "
            f"shown={len(self._shown)}/{self.rep_win}"
        )
