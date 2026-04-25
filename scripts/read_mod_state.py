"""mod가 client_log.txt에 기록한 JSON을 읽어 GameState로 변환."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from game_state import GameState, from_raw

LOG_PATH = Path(__file__).parent.parent / "game_logs" / "client_log.txt"
PREFIX   = "[HINT_SYSTEM_STATE]"


def parse_last_state(log_path: Path) -> dict | None:
    """로그에서 마지막 HINT_SYSTEM_STATE JSON을 파싱."""
    last = None
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if PREFIX in line:
                idx = line.index(PREFIX) + len(PREFIX)
                try:
                    last = json.loads(line[idx:].strip())
                except json.JSONDecodeError:
                    pass
    return last


def load_state(log_path: Path = LOG_PATH) -> GameState | None:
    raw = parse_last_state(log_path)
    if raw is None:
        return None
    return from_raw(raw)


def print_state(state: GameState):
    print(f"Day {state.day} ({state.day_bucket})  |  {state.time_of_day}")
    print(f"  HP={state.health_level}  SAN={state.sanity_level}  HUN={state.hunger_level}")
    print(f"  science={state.science_unlocked}  armor={state.has_armor}")
    print(f"  자원 부족: grass={state.grass_low}  twigs={state.twigs_low}")
    print(f"  spider_drops={state.has_spider_drops}  gold={state.has_gold}  chester={state.has_chester}")
    print(f"  in_cave={state.in_cave}  inv_full={state.inventory_full}")


if __name__ == "__main__":
    log = Path(sys.argv[1]) if len(sys.argv) > 1 else LOG_PATH
    state = load_state(log)
    if state is None:
        print("로그에서 게임 상태를 찾을 수 없습니다.")
    else:
        print_state(state)
