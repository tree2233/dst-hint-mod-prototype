"""
live_hint.py — 실제 게임 client.log를 읽어 SBERT 힌트를 스티커 메모 오버레이로 표시.

실행:
    Windows Python:  py scripts/live_hint.py
    WSLg 환경:       python3 scripts/live_hint.py   (sudo apt install python3-tk 필요)

의존:
    pip install sentence-transformers scikit-learn
"""
import sys
import tkinter as tk
from pathlib import Path

# dst-hint-system/ 과 scripts/ 를 모두 경로에 추가
_ROOT    = Path(__file__).parent.parent
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_SCRIPTS))

from read_mod_state import load_state, LOG_PATH          # scripts/read_mod_state.py
from experiment import (                                  # scripts/experiment.py
    load_hints, recommend_onehot, recommend_sbert,
)
from sentence_transformers import SentenceTransformer

MODEL_NAME   = "paraphrase-multilingual-MiniLM-L12-v2"
AUTO_REFRESH = 30_000    # ms — 자동 새로고침 (0 이면 비활성)

# ── 색상 팔레트 ───────────────────────────────────────────────────────────────
C = dict(
    title_bg = "#F0D020",
    body_bg  = "#FFFACD",
    foot_bg  = "#C8A800",
    fg       = "#1E1E1E",
    foot_fg  = "#FFFFFF",
    hover    = "#FFE050",
)


class HintOverlay(tk.Tk):
    W, H = 370, 200

    def __init__(self, hints, model, hint_embs):
        super().__init__()
        self.hints     = hints
        self.model     = model
        self.hint_embs = hint_embs
        self._ox = self._oy = 0
        self._job = None

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha",   0.94)
        self.geometry(f"{self.W}x{self.H}+80+80")
        self.configure(bg=C["body_bg"])

        self._build()
        self.refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # 타이틀 바
        bar = tk.Frame(self, bg=C["title_bg"], height=28)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        title_lbl = tk.Label(
            bar, text="  DST 힌트 시스템",
            bg=C["title_bg"], fg=C["fg"],
            font=("Malgun Gothic", 10, "bold"),
        )
        title_lbl.pack(side=tk.LEFT, pady=4)

        for txt, cmd in [("✕", self.destroy), ("↺", self.refresh)]:
            tk.Button(
                bar, text=txt, command=cmd,
                bg=C["title_bg"], fg=C["fg"],
                activebackground=C["hover"],
                relief="flat", bd=0,
                font=("Malgun Gothic", 11),
                cursor="hand2", padx=6,
            ).pack(side=tk.RIGHT, pady=2)

        # 드래그 바인딩
        for w in (bar, title_lbl):
            w.bind("<ButtonPress-1>",
                   lambda e: (setattr(self, "_ox", e.x), setattr(self, "_oy", e.y)))
            w.bind("<B1-Motion>",
                   lambda e: self.geometry(
                       f"+{self.winfo_x()+e.x-self._ox}"
                       f"+{self.winfo_y()+e.y-self._oy}"))

        # 힌트 텍스트
        self.text_var = tk.StringVar(value="로딩 중...")
        self._body = tk.Label(
            self, textvariable=self.text_var,
            bg=C["body_bg"], fg=C["fg"],
            font=("Malgun Gothic", 10),
            wraplength=self.W - 24, justify="left",
            padx=12, pady=8, anchor="nw",
        )
        self._body.pack(fill=tk.BOTH, expand=True)

        # 하단 상태 표시
        self.status_var = tk.StringVar()
        tk.Label(
            self, textvariable=self.status_var,
            bg=C["foot_bg"], fg=C["foot_fg"],
            font=("Malgun Gothic", 8),
            padx=8, pady=3, anchor="w",
        ).pack(fill=tk.X)

    # ── 새로고침 ──────────────────────────────────────────────────────────────

    def refresh(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None

        state = load_state(LOG_PATH)
        if state is None:
            self.text_var.set("게임 상태를 읽을 수 없습니다.\n로그 파일 경로를 확인하세요.")
            self.status_var.set("오류: 로그에서 상태 없음")
        else:
            oh = recommend_onehot(state, self.hints, top_k=1)
            sb = recommend_sbert(state, self.hints, self.model, self.hint_embs, top_k=1)

            hint_id, sb_sc, text = sb[0]
            oh_id,   oh_sc, _   = oh[0]

            self.text_var.set(text)
            self.status_var.set(
                f"Day {state.day}  {state.time_of_day}   │   "
                f"SBERT: {hint_id} ({sb_sc:.2f})   One-hot: {oh_id} ({oh_sc:.2f})"
            )

            # 텍스트 길이에 따라 창 높이 자동 조절
            self.update_idletasks()
            needed = self._body.winfo_reqheight() + 28 + 22
            self.geometry(f"{self.W}x{max(self.H, min(needed + 16, 320))}")

        if AUTO_REFRESH > 0:
            self._job = self.after(AUTO_REFRESH, self.refresh)


def main():
    print("SBERT 모델 로딩 중...")
    hints     = load_hints()
    model     = SentenceTransformer(MODEL_NAME)
    hint_embs = model.encode([h["text"] for h in hints], show_progress_bar=False)
    print(f"힌트 {len(hints)}개 인코딩 완료.")
    print(f"로그 경로: {LOG_PATH}")
    print(f"자동 새로고침: {AUTO_REFRESH//1000}초  (0으로 설정 시 비활성)")

    HintOverlay(hints, model, hint_embs).mainloop()


if __name__ == "__main__":
    main()
