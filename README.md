# DST Hint System — 인게임 힌트 추천 프로토타입

Don't Starve Together(DST) 게임 상태를 실시간으로 분석해, 초보 플레이어에게 **맥락에 맞는 힌트**를 추천하는 테스트 시스템입니다.

초반 가을 1~15일차 사이 매우 작은 기간에 제한된 정보를 기준으로 플레이어에게 다음 행동을 추천합니다.

---

## 구성 요소

```
dst-hint-system/
├── dst_hint_mod/          # DST 클라이언트 모드 (Lua)
│   ├── modmain.lua        #   상태 수집 + 로그 출력 메인
│   └── modinfo.lua        #   모드 메타데이터 / 설정 옵션
├── game_logs/
│   └── client_log.txt     # 실제 게임 실행 샘플 로그
├── data/
│   └── hints.json         # 힌트 데이터베이스 (h01–h10)
├── game_state.py          # GameState 데이터클래스 + JSON 파서
├── context_engine.py      # 맥락 기반 쿼리 보정 엔진
├── scripts/
│   ├── read_mod_state.py  # 로그 파싱 → GameState 변환
│   ├── experiment.py      # One-hot / SBERT / SBERT+Context 비교 실험
│   └── terminal_hint.py   # 실시간 터미널 힌트 출력 (게임 연동)
└── requirements.txt
```

---

## 추천 방식 비교

| 방식 | 설명 |
|---|---|
| **One-hot** | 태그 기반 다중 핫 벡터 + 코사인 유사도. 속도 빠름, 의미 이해 없음 |
| **SBERT** | `paraphrase-multilingual-MiniLM-L12-v2`로 게임 상태 텍스트를 임베딩 후 힌트와 유사도 계산 |
| **SBERT + Context** | SBERT에 Context Engine 보정 추가 (아래 참조) |

### Context Engine

`context_engine.py` 는 세 가지 보정을 결합합니다.

| 보정 | 활성 조건 | 효과 |
|---|---|---|
| Delta embedding | 10 s ≤ interval ≤ 60 s | 직전→현재 상태 **변화 방향**을 쿼리에 더해 상황 악화를 강조 |
| Decaying centroid | interval ≥ 10 s | 최근 N개 state의 지수 감쇠 **무게중심**을 더해 플레이 흐름 반영 |
| Anti-repetition | 항상 | 이미 제시된 힌트 방향을 쿼리에서 밀어내고, 점수도 직접 감쇠 |

`terminal_hint.py --interval <초>` 옵션으로 모드 내보내기 주기를 지정하면 자동으로 보정 범위가 조정됩니다.

---

## 모드 설치 (dst_hint_mod)

1. `dst_hint_mod/` 폴더 전체를 DST 모드 디렉터리에 복사합니다.
   - Windows: `Documents\Klei\DoNotStarveTogether\mods\dst_hint_mod\`
2. 게임 내 모드 메뉴에서 **DST Hint System - State Exporter** 활성화
3. 게임 실행 중 상태가 `client_log.txt` 에 `[HINT_SYSTEM_STATE]{...}` 형식으로 기록됩니다.

모드 설정 옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| Export Interval | 10 s | 자동 상태 내보내기 주기 |
| Nearby Radius | 15 | 주변 개체 탐색 반경 |
| Show Notification | Yes | 내보내기 시 게임 내 알림 |
| Manual Export Key | H | 즉시 내보내기 단축키 |

---

## 실행

### 의존성 설치

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 실험 실행 (One-hot vs SBERT vs SBERT+Context)

```bash
python3 scripts/experiment.py
```

가상 케이스 4개(Cases A–D)와 시퀀스 2개(Seq 1–2)에 대한 추천 결과를 출력합니다.

### 실시간 터미널 힌트 (게임 연동)

게임을 실행한 상태에서:

```bash
python3 scripts/terminal_hint.py
# 또는 모드 내보내기 주기를 명시적으로 지정
python3 scripts/terminal_hint.py --interval 10
```

게임 상태가 변할 때마다 세 방식의 추천 결과를 자동으로 출력합니다. `Ctrl+C` 로 종료합니다.

```
════════════════════════════════════════════════════════════════════════════
  [00:01:20]  Day 3  DUSK  │  HP:ok  SAN:ok  HUN:ok
  쿼리: 황혼 저녁. 생존 자원 확인 필요.
────────────────────────────────────────────────────────────────────────────
  One-hot        h05 (0.71)  11일이 지났는데 방어구가 없다. 이 시점부터...
  SBERT          h07 (0.42)  밤이 다가오는데 풀이나 잔가지가 부족하다...
  SBERT+Context  h09 (0.38)  인벤토리가 가득 찼다. 탐험하다 보면...
════════════════════════════════════════════════════════════════════════════
```

---

## 힌트 데이터 (data/hints.json)

현재 h01–h10, 총 10개의 힌트가 포함되어 있습니다.

| ID | 주요 상황 |
|---|---|
| h01 | 정신력 critical/low |
| h02 | 체력 low + 거미 전투 + 과학 기계 없음 |
| h03 | 체력 low + 거미 전투 + 방어구 없음 |
| h04 | 황혼 + 풀/잔가지 부족 |
| h05 | 11일 이후 + 방어구 없음 (하운드 경고) |
| h06 | 배고픔 low + 괴물고기 보유 |
| h07 | 황혼 + 자원 부족 + 동굴 밖 |
| h08 | 인벤토리 가득 + 금 있음 + 과학 기계 없음 |
| h09 | 인벤토리 가득 + Chester 없음 |
| h10 | 인벤토리 가득 + Chester 있음 |

---

## 한계 및 향후 방향

- **Wildcard 편향**: 태그가 많이 `any`인 힌트(h05)가 One-hot 코사인 점수에서 과도하게 높은 점수를 얻음
- **Anti-repeat 과억제**: 긴급 힌트(h01 정신력 위기)가 anti-repeat에 의해 재차 억제되는 문제 — 임계값 기반 억제 면제 필요
- **힌트 DB 확장**: 현재 10개는 실험용. 실제 서비스 수준에서는 수십~수백 개 필요
- **숙련자 데이터 학습**: 모드로 수집한 숙련자 플레이 데이터를 바탕으로 직접 추천 모델을 학습시키면 Context Engine 하드코딩 이상의 성능을 기대할 수 있음
- **커뮤니티 정보 필터링**: 자체 추천보다 위키/포럼 검색 결과를 게임 상태에 맞게 필터링하는 방식도 실용적인 대안

---

## 개발 환경

- Python 3.10+
- `sentence-transformers`, `scikit-learn`, `numpy`
