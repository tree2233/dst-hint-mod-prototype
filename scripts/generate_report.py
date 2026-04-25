"""generate_report.py — DST 힌트 시스템 실험 보고서 PDF 생성"""
import io
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 ──────────────────────────────────────────────────────────────────────
FONT_R = "/mnt/c/Windows/Fonts/malgun.ttf"
FONT_B = "/mnt/c/Windows/Fonts/malgunbd.ttf"
OUTPUT = Path(__file__).parent.parent / "DST_Hint_System_Report.pdf"

pdfmetrics.registerFont(TTFont("MG",  FONT_R))
pdfmetrics.registerFont(TTFont("MGB", FONT_B))
_fp  = fm.FontProperties(fname=FONT_R)
_fpb = fm.FontProperties(fname=FONT_B)
plt.rcParams["axes.unicode_minus"] = False

# ── 색상 ──────────────────────────────────────────────────────────────────────
NAVY  = colors.HexColor("#1a3a5c")
BLUE  = colors.HexColor("#2c6fad")
LGRAY = colors.HexColor("#f0f4f8")
DGRAY = colors.HexColor("#888888")
GREEN = colors.HexColor("#c8f0d4")

# ── ReportLab 스타일 ──────────────────────────────────────────────────────────
def _s(name, **kw):
    base = dict(fontName="MG", fontSize=10, leading=16, spaceAfter=5)
    base.update(kw)
    return ParagraphStyle(name, **base)

S = {
    "title":  _s("T",  fontSize=22, fontName="MGB", leading=28, spaceAfter=2, textColor=NAVY),
    "sub":    _s("S",  fontSize=12, textColor=DGRAY, spaceAfter=2),
    "meta":   _s("M",  fontSize=9,  textColor=DGRAY, spaceAfter=0),
    "h1":     _s("H1", fontSize=15, fontName="MGB", spaceBefore=16, spaceAfter=5, textColor=NAVY),
    "h2":     _s("H2", fontSize=11, fontName="MGB", spaceBefore=10, spaceAfter=4, textColor=BLUE),
    "body":   _s("B",  fontSize=10, leading=17, spaceAfter=6),
    "bullet": _s("BL", fontSize=10, leading=16, leftIndent=14, spaceAfter=3, bulletIndent=4),
    "cap":    _s("C",  fontSize=8,  textColor=DGRAY, spaceAfter=8, alignment=1),
}

def HR(): return HRFlowable(width="100%", thickness=0.5, color=DGRAY, spaceAfter=8)
def SP(n=6): return Spacer(1, n)
def P(t, skey="body"): return Paragraph(t, S[skey])
def BL(t): return Paragraph(f"• {t}", S["bullet"])

# ── 실험 결과 (실제 실행 값 하드코딩) ─────────────────────────────────────────
RES = {
    "A": {
        "case":  "Case A — 정신력 위기 (완전 일치)",
        "state": "sanity=critical, 기타 수치 정상",
        "query": "정신력이 위험하게 낮다.",
        "oh": [("h01", 0.66), ("h05", 0.66), ("h02", 0.59)],
        "sb": [("h01", 0.40), ("h06", 0.23), ("h02", 0.23)],
        "ok": "h01",
    },
    "B": {
        "case":  "Case B — 거미 전투 (구조 제약)",
        "state": "spider=yes, health=low, science=no",
        "query": "체력이 낮다. 거미 아이템 보유. 과학 기계 미해금. 방어구 없음.",
        "oh": [("h02", 0.68), ("h05", 0.66), ("h03", 0.65)],
        "sb": [("h03", 0.65), ("h06", 0.54), ("h02", 0.53)],
        "ok": "h02",
    },
    "C": {
        "case":  "Case C — 태그 불일치 (wildcard 편향)",
        "state": "health=low, science=no, spider=NO",
        "query": "체력이 낮다. 과학 기계 미해금. 방어구 없음.",
        "oh": [("h05", 0.66), ("h02", 0.63), ("h01", 0.61)],
        "sb": [("h03", 0.52), ("h05", 0.52), ("h02", 0.51)],
        "ok": "h02",
    },
    "D": {
        "case":  "Case D — 복합 불일치 (SBERT 의미론적 탐색)",
        "state": "inv_full=yes, science=no, gold=NO, chester=NO",
        "query": "과학 기계 미해금. 인벤토리 가득 참.",
        "oh": [("h05", 0.66), ("h09", 0.63), ("h08", 0.63)],
        "sb": [("h08", 0.64), ("h02", 0.61), ("h06", 0.55)],
        "ok": "h08",
    },
}

ANALYSES = {
    "A": (
        "One-hot과 SBERT 모두 h01을 1위로 선택하였다. "
        "to_text() 개선(전투·체력 위기와 무관하면 과학/방어구 정보 제외)으로 "
        "SBERT 쿼리가 \"정신력이 위험하게 낮다.\" 단문으로 단순화되어 "
        "h01(\"정신력이 낮다...\")에 대한 유사도가 명확히 높게 나타났다(Top-1: 0.40, 2위: 0.23). "
        "One-hot 역시 sanity=critical 태그가 h01에 직접 매핑되어 정확히 동작하였다."
    ),
    "B": (
        "One-hot은 h02를 1위(0.68)로 정확히 선택하였다. h03는 science=yes 태그를 요구하나 "
        "현재 상태는 science=no이므로 태그 불일치 패널티가 발생해 순위가 낮아진다. "
        "반면 SBERT는 쿼리에 포함된 \"방어구가 없다\"가 h03 텍스트와 직접 매칭되어 "
        "h03를 1위(0.65)로 선택하였다. h03는 과학 기계가 이미 있다고 가정하는 힌트이므로 "
        "science=no 상황의 플레이어에게 실행 불가능하다. "
        "이 케이스에서 One-hot의 구조적 제약 이해 능력이 SBERT보다 우수함을 확인하였다."
    ),
    "C": (
        "One-hot은 h05(0.66)를 1위로 선택하였는데, h05는 \"11일이 지났는데 방어구가 없다\"는 "
        "힌트로 Day 3 플레이어와 완전히 무관하다. h05가 armor=no, time=day, day=11-15를 "
        "제외한 모든 태그를 \"any\" 와일드카드로 가지므로 벡터 노름이 작아져 코사인 점수가 "
        "구조적으로 과대평가된다(wildcard bias: √28 ≈ 5.29). "
        "SBERT는 h03(0.52)를 1위로 선택하였다. h03 역시 완벽한 정답은 아니나 "
        "전투·체력 맥락에서 의미론적으로 유사하여 One-hot의 h05보다 관련성이 높다."
    ),
    "D": (
        "이 케이스에서 SBERT의 의미론적 탐색 능력이 가장 명확하게 드러났다. "
        "인벤토리 관련 힌트는 모두 태그 불일치가 있으며(h08: gold=yes 불일치, h09: science=yes 불일치), "
        "One-hot은 또다시 wildcard bias로 h05(0.66)를 1위로 선택하였다. "
        "반면 SBERT는 쿼리 \"과학 기계 미해금. 인벤토리 가득 참.\"이 "
        "h08 텍스트(\"인벤토리가 가득 찼고... 과학 기계를 만들어라... 인벤토리가 8칸 늘어난다\")와 "
        "두 키워드 모두 의미적으로 일치하여 h08을 1위(0.64)로 정확히 선택하였다."
    ),
}


# ── Figure 1: 그룹 막대 차트 ──────────────────────────────────────────────────
def make_fig1() -> io.BytesIO:
    cases  = list(RES.keys())
    oh_ids = [RES[c]["oh"][0][0] for c in cases]
    sb_ids = [RES[c]["sb"][0][0] for c in cases]
    oh_sc  = [RES[c]["oh"][0][1] for c in cases]
    sb_sc  = [RES[c]["sb"][0][1] for c in cases]
    oks    = [RES[c]["ok"]       for c in cases]

    BLU = "#2c6fad"; BLU2 = "#a8c8e8"
    ONG = "#e07020"; ONG2 = "#f0c090"

    x = [0, 1.3, 2.6, 3.9]
    w = 0.5
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    for i, c in enumerate(cases):
        oh_ok = oh_ids[i] == oks[i]
        sb_ok = sb_ids[i] == oks[i]
        ax.bar(x[i]-w/2, oh_sc[i], w, color=BLU if oh_ok else BLU2,
               edgecolor="white", linewidth=1.2, zorder=3)
        ax.bar(x[i]+w/2, sb_sc[i], w, color=ONG if sb_ok else ONG2,
               edgecolor="white", linewidth=1.2, zorder=3)
        ax.text(x[i]-w/2, oh_sc[i]+0.012, oh_ids[i],
                ha="center", va="bottom", fontsize=9,
                fontproperties=_fpb, color="#1a3a5c")
        ax.text(x[i]+w/2, sb_sc[i]+0.012, sb_ids[i],
                ha="center", va="bottom", fontsize=9,
                fontproperties=_fpb, color="#7a2800")

    xlabels = ["Case A\n정신력 위기", "Case B\n거미 전투",
               "Case C\n태그 불일치", "Case D\n복합 불일치"]
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, fontproperties=_fp, fontsize=9.5)
    ax.set_ylabel("코사인 유사도 (Top-1)", fontproperties=_fp, fontsize=10)
    ax.set_ylim(0, 0.85)
    ax.set_title("One-hot vs SBERT: 케이스별 Top-1 코사인 유사도",
                 fontproperties=_fpb, fontsize=11.5, pad=10)
    ax.grid(axis="y", alpha=0.35, linestyle="--", zorder=0)
    ax.spines[["top", "right"]].set_visible(False)

    legend = [
        mpatches.Patch(color=BLU,  label="One-hot  (정답)"),
        mpatches.Patch(color=BLU2, label="One-hot  (오답)"),
        mpatches.Patch(color=ONG,  label="SBERT  (정답)"),
        mpatches.Patch(color=ONG2, label="SBERT  (오답)"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=9,
              prop=_fp, framealpha=0.93)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf


# ── Table 1: Top-3 결과 비교 ──────────────────────────────────────────────────
def make_table1():
    header = ["케이스", "방법", "1위", "2위", "3위"]
    rows   = [header]
    bg_cmds = []
    ri = 1

    for key in ["A", "B", "C", "D"]:
        r  = RES[key]
        ok = r["ok"]
        for mi, (method, hits) in enumerate([("One-hot", r["oh"]), ("SBERT", r["sb"])]):
            row = [key if mi == 0 else "", method]
            for ci, (hid, sc) in enumerate(hits):
                row.append(f"{hid} {'✓' if hid==ok else '✗'} ({sc:.2f})")
                if hid == ok:
                    bg_cmds.append(("BACKGROUND", (ci+2, ri), (ci+2, ri), GREEN))
            rows.append(row)
            ri += 1

    cmds = [
        ("FONTNAME",      (0, 0), (-1, -1), "MG"),
        ("FONTNAME",      (0, 0), (-1,  0), "MGB"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("FONTSIZE",      (0, 0), (-1,  0), 9),
        ("BACKGROUND",    (0, 0), (-1,  0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1,  0), colors.white),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("GRID",          (0, 0), (-1, -1), 0.35, DGRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LGRAY]),
        ("SPAN", (0, 1), (0, 2)),   # Case A
        ("SPAN", (0, 3), (0, 4)),   # Case B
        ("SPAN", (0, 5), (0, 6)),   # Case C
        ("SPAN", (0, 7), (0, 8)),   # Case D
        ("VALIGN", (0, 1), (0, -1), "MIDDLE"),
    ] + bg_cmds

    tbl = Table(rows, colWidths=[1.6*cm, 2.2*cm, 4.7*cm, 4.7*cm, 4.7*cm])
    tbl.setStyle(TableStyle(cmds))
    return tbl


# ── PDF 조립 ──────────────────────────────────────────────────────────────────
def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm,  bottomMargin=2.5*cm,
    )
    story = []

    # ── 표지 정보 ─────────────────────────────────────────────────────────────
    story += [
        P("DST 인게임 힌트 시스템", "title"),
        P("NLP 기반 One-hot vs SBERT 힌트 추천 비교 실험", "sub"),
        SP(4),
        P("Term Project #1 &nbsp;&nbsp;|&nbsp;&nbsp; 20211440 정보현", "meta"),
        SP(2), HR(), SP(4),
    ]

    # ── Summary ───────────────────────────────────────────────────────────────
    story.append(P("Summary", "h1"))
    story.append(P(
        "Don't Starve Together(DST)는 높은 난이도로 초보 플레이어 대부분이 초반 15일(첫 번째 가을) "
        "이내에 사망하는 생존 게임이다. 본 연구는 Lua 게임 모드를 통해 플레이어의 실시간 상태(체력·정신력·"
        "인벤토리·시간대 등 14개 특성)를 추출하고, NLP 기반 힌트 추천 시스템을 구축하여 두 가지 "
        "임베딩 방식을 비교한다. "
        "(1) 태그 기반 One-hot 인코딩 + 코사인 유사도, "
        "(2) 다국어 SBERT(paraphrase-multilingual-MiniLM-L12-v2) 의미론적 유사도. "
        "초반 15일 위기 상황에 특화된 10개의 한국어 힌트를 설계하고, "
        "완전 일치(Case A·B)와 태그 불일치(Case C·D) 4가지 테스트 케이스로 비교 실험을 수행하였다."
    ))
    story.append(P(
        "<b>주요 발견:</b> One-hot은 구조적 제약 조건이 명확할 때 우수하나(Case B: 과학 기계 미해금 상황에서 "
        "science=yes 필요 힌트 자동 제외), \"any\" 와일드카드 태그가 많은 힌트가 구조적으로 점수 과대평가되는 "
        "wildcard bias가 발생하여 무관한 힌트(h05: 11일차 하운드 경고)를 반복 선택한다(Case C·D). "
        "SBERT는 태그 불일치 상황에서도 의미론적 유사도로 적절한 힌트를 탐색하며(Case D: "
        "인벤토리 관련 h08 정확히 선택), 두 방법의 상호보완적 특성을 확인하였다."
    ))
    story.append(P(
        "<b>결론:</b> 소규모 힌트 셋에서는 태그 기반 방법이 구조적 정확성을 제공하지만 wildcard bias에 "
        "취약하며, SBERT는 텍스트 의미 기반 강건성으로 이를 보완한다. "
        "향후 하이브리드 접근법과 힌트 규모 확장이 기대된다."
    ))
    story.append(SP(4))

    # ── Introduction ──────────────────────────────────────────────────────────
    story.append(P("1. Introduction", "h1"))
    story.append(P(
        "Don't Starve Together(DST)는 Klei Entertainment가 개발한 멀티플레이어 생존 게임으로, "
        "음식·체력·정신력을 동시에 관리하며 자연 환경과 몬스터의 위협에 대응해야 한다. "
        "진입 장벽이 매우 높아 초보 플레이어는 대부분 첫 번째 가을(1~15일) 안에 사망하며, "
        "주요 원인은 야간 어둠 처리 실패, 거미·하운드 전투에서의 체력 소진, "
        "굶주림, 과학 기계 미해금으로 인한 장비 부재 등이다."
    ))
    story.append(P(
        "기존의 공식 튜토리얼이나 위키는 상황과 무관한 정보를 일방적으로 제공하며, "
        "플레이어가 직면한 즉각적인 위기에 대한 맥락적 조언을 제시하지 못한다. "
        "이 문제를 해결하기 위해 본 연구는 게임 내 상태를 실시간으로 추출하고 "
        "NLP 기반으로 가장 적절한 힌트를 추천하는 시스템을 구축한다."
    ))
    story.append(P("<b>연구 목표</b>", "h2"))
    story += [
        BL("Lua 게임 모드와 Python 파이프라인을 연동하여 14개 특성의 실시간 게임 상태 추출"),
        BL("One-hot 인코딩 기반 구조적 추천과 SBERT 기반 의미론적 추천의 성능 비교"),
        BL("각 방법의 강점·한계를 체계적 실험으로 검증하여 향후 하이브리드 설계에 기여"),
        SP(4),
    ]

    # ── Methods ───────────────────────────────────────────────────────────────
    story.append(P("2. Methods", "h1"))

    story.append(P("2.1 시스템 파이프라인", "h2"))
    story.append(P(
        "전체 시스템은 세 단계로 구성된다. "
        "(1) <b>상태 추출:</b> Lua 모드(dst_hint_mod)가 플레이어 상태를 JSON으로 client_log.txt에 기록하면 "
        "Python 파서가 이를 읽어 GameState 데이터클래스로 변환한다. "
        "(2) <b>임베딩 계산:</b> 상태를 One-hot 벡터 또는 자연어 텍스트로 변환하여 유사도를 계산한다. "
        "(3) <b>힌트 추천:</b> 코사인 유사도 상위 k개 힌트를 반환한다."
    ))

    story.append(P("2.2 게임 상태 추출 (GameState)", "h2"))
    story.append(P(
        "GameState 데이터클래스는 14개 특성을 포함한다: "
        "체력/정신력/배고픔 수준(critical &lt;25% / low &lt;50% / ok), "
        "과학 기계 해금 여부, 방어구 보유, 자원 부족(풀·잔가지 ≤5개), "
        "거미 아이템(괴물고기/거미젤리/실크) 보유, 금·Chester 보유, "
        "인벤토리 포화(본체 15칸), 동굴 여부, 시간대(낮/황혼/밤), 생존 일수."
    ))

    story.append(P("2.3 힌트 데이터베이스", "h2"))
    story.append(P(
        "초반 15일 동안 가장 빈번한 위기 상황에 기반하여 10개의 한국어 힌트(h01~h10)를 설계하였다. "
        "각 힌트는 텍스트 설명과 14개 특성에 대한 조건 태그(특정 값 또는 \"any\" 와일드카드)를 가진다. "
        "커버하는 상황: 정신력 위기(h01), 거미전투+체력+과학 미해금(h02), "
        "거미전투+방어구 없음(h03), 황혼+자원 부족(h04/h07), 11일차 하운드 경고(h05), "
        "배고픔+요리솥(h06), 인벤토리 포화 관리(h08/h09/h10)."
    ))

    story.append(P("2.4 One-hot 추천 방식", "h2"))
    story.append(P(
        "14개 GameState 특성을 35차원 이진 벡터로 인코딩한다. "
        "힌트 태그는 multi-hot 벡터로 변환되며, \"any\" 와일드카드는 해당 차원 전체를 1로 설정한다. "
        "상태 벡터와 모든 힌트 벡터 간 코사인 유사도를 계산하여 상위 k개를 반환한다. "
        "구조적 제약 조건을 태그 레벨에서 명확히 처리할 수 있으나, "
        "와일드카드가 많은 힌트일수록 벡터 노름이 작아져 코사인 점수가 구조적으로 과대평가된다."
    ))

    story.append(P("2.5 SBERT 추천 방식", "h2"))
    story.append(P(
        "paraphrase-multilingual-MiniLM-L12-v2 모델(한국어 지원)을 사용한다. "
        "to_text() 함수가 GameState를 자연어 설명문으로 변환하며, "
        "전투·체력 위기·인벤토리 문제와 무관한 경우 과학 기계/방어구 정보를 쿼리에서 제외하여 노이즈를 줄인다. "
        "힌트 텍스트를 미리 인코딩하고, 쿼리 임베딩과의 코사인 유사도로 상위 k개 힌트를 반환한다."
    ))

    story.append(P("2.6 실험 설계", "h2"))
    story.append(P(
        "GitHub 저장소: <u>https://github.com/[your-username]/dst-hint-system</u>"
    ))
    story.append(P(
        "4가지 테스트 케이스를 설계하였다: "
        "<b>Case A</b> — 정신력 위기(완전 일치, 양 방법 일치 예상), "
        "<b>Case B</b> — 거미전투(완전 일치, 구조 제약 조건 검증), "
        "<b>Case C</b> — 태그 불일치(spider 없는 체력 위기, wildcard 편향 분석), "
        "<b>Case D</b> — 복합 불일치(인벤토리 가득+gold/chester 없음, 의미론적 탐색 검증)."
    ))
    story.append(SP(4))

    # ── Results ───────────────────────────────────────────────────────────────
    story.append(P("3. Results", "h1"))

    buf = make_fig1()
    story.append(KeepTogether([
        Image(buf, width=14.5*cm, height=7.8*cm),
        P("Figure 1.  케이스별 Top-1 코사인 유사도. "
          "진한 색 = 정답 힌트 선택, 연한 색 = 오답 힌트 선택. "
          "막대 위 레이블은 선택된 힌트 ID.", "cap"),
    ]))
    story.append(SP(4))

    story.append(P("Table 1.  케이스별 Top-3 추천 결과 (✓ 정답 / ✗ 오답 / 녹색 음영 = 정답 셀)", "cap"))
    story.append(make_table1())
    story.append(SP(10))

    story.append(P("3.1 케이스별 분석", "h2"))
    for key in ["A", "B", "C", "D"]:
        r = RES[key]
        story.append(P(f"<b>{r['case']}</b> — 상태: {r['state']}"))
        story.append(P(ANALYSES[key]))
        story.append(SP(4))

    story.append(PageBreak())

    # ── Discussion ────────────────────────────────────────────────────────────
    story.append(P("4. Discussion", "h1"))

    story.append(P("4.1 One-hot 방식의 강점과 한계", "h2"))
    story.append(P(
        "One-hot 방식은 구조적 제약 조건을 태그 레벨에서 명시적으로 처리한다는 강점이 있다. "
        "Case B에서 science=no 상태의 플레이어에게 과학 기계가 필요한 h03를 자동으로 낮은 순위로 배치한 것이 그 예이다. "
        "그러나 \"any\" 와일드카드 태그가 많은 힌트가 구조적으로 높은 코사인 유사도를 갖는 "
        "<b>wildcard bias</b> 문제가 심각하다. "
        "h05는 armor=no, time=day, day=11-15를 제외한 모든 태그가 \"any\"이므로 벡터 노름이 "
        "√28≈5.29로 작아 Day 3 플레이어에게도 0.66이라는 높은 점수를 반복 획득한다. "
        "이 문제는 힌트 수가 증가할수록 더욱 심화될 것이다."
    ))

    story.append(P("4.2 SBERT 방식의 강점과 한계", "h2"))
    story.append(P(
        "SBERT는 태그 불일치 상황에서도 텍스트의 의미론적 유사성으로 적절한 힌트를 탐색한다. "
        "Case D에서 태그가 완전히 일치하는 힌트가 없는 상황에서도 h08을 정확히 선택한 것이 대표적이다. "
        "힌트 규모가 확장될수록 SBERT 방식이 더 유리한데, "
        "100개 이상의 힌트에서는 태그 설계 없이도 의미 기반 검색이 가능하기 때문이다. "
        "그러나 Case B에서처럼 구조적 실행 가능성(science=no이면 과학 기계 이용 불가)을 "
        "텍스트 의미로부터 추론하지 못하는 한계가 있다."
    ))

    story.append(P("4.3 상호보완성과 하이브리드 접근법", "h2"))
    story.append(P(
        "두 방식은 상호보완적이다. One-hot을 사전 필터(실행 불가능 힌트 제거)로, "
        "SBERT를 최종 의미론적 랭킹으로 활용하는 하이브리드 접근법이 유망하다. "
        "또한 wildcard bias 완화를 위해 태그 특이성(specificity)에 비례한 가중치 부여나 "
        "TF-IDF 스타일의 인버스 빈도 정규화 도입을 고려할 수 있다."
    ))
    story.append(SP(4))

    # ── Conclusion ────────────────────────────────────────────────────────────
    story.append(P("5. Conclusion", "h1"))
    story.append(P(
        "본 연구는 DST 인게임 힌트 시스템을 통해 One-hot 태그 매칭과 SBERT 의미론적 임베딩 두 가지 "
        "추천 방식을 비교하였다."
    ))
    story += [
        BL("완전 일치 케이스(Case A)에서 양 방법 모두 정답 h01을 선택하였다."),
        BL("One-hot은 구조적 제약 조건(science 해금 여부) 처리에 강점을 보인다(Case B)."),
        BL("One-hot의 wildcard bias는 Day 3 상황에서 Day 11 힌트(h05)를 반복 선택하는 오류를 야기한다(Case C·D)."),
        BL("SBERT는 태그 불일치 상황에서 의미론적 유사도로 더 적절한 힌트를 선택한다(Case D)."),
        SP(4),
    ]
    story.append(P(
        "<b>향후 방향:</b> (1) One-hot 사전 필터 + SBERT 최종 랭킹의 하이브리드 시스템, "
        "(2) 힌트 100개 이상으로 확장하여 SBERT 스케일 우위 검증, "
        "(3) 세션 기반 반복 힌트 억제 메커니즘, "
        "(4) 사용자 피드백 기반 온라인 학습 도입."
    ))
    story.append(SP(4))

    # ── References ────────────────────────────────────────────────────────────
    story.append(HR())
    story.append(P("References", "h1"))
    refs = [
        "Reimers, N., &amp; Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using "
        "Siamese BERT-Networks. <i>Proceedings of EMNLP 2019.</i>",
        "Devlin, J., Chang, M.-W., Lee, K., &amp; Toutanova, K. (2019). BERT: Pre-training of "
        "Deep Bidirectional Transformers for Language Understanding. <i>NAACL 2019.</i>",
        "Klei Entertainment. (2013). <i>Don't Starve Together.</i> [Video Game].",
        "Don't Starve Wiki Contributors. (2024). Don't Starve Together Official Wiki. "
        "https://dontstarve.fandom.com/",
        "Hugging Face. (2024). paraphrase-multilingual-MiniLM-L12-v2. "
        "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. "
        "<i>Journal of Machine Learning Research, 12</i>, 2825-2830.",
    ]
    for i, r in enumerate(refs, 1):
        story.append(P(f"[{i}]  {r}", "bullet"))
        story.append(SP(2))

    doc.build(story)
    print(f"보고서 저장 완료: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
