"""
GameState: 클라이언트 로그에서 추출한 게임 상태.
"""
from dataclasses import dataclass


def _level(percent: int) -> str:
    if percent < 25:  return "critical"
    if percent < 50:  return "low"
    return "ok"


def _count(items: list, prefab: str) -> int:
    return sum(it.get("stack", 1) for it in items if it.get("prefab") == prefab)


def _has_any(items: list, prefabs: set) -> bool:
    return any(it.get("prefab") in prefabs for it in items)


@dataclass
class GameState:
    # 생존 수치
    health_level: str    # critical / low / ok
    sanity_level: str
    hunger_level: str

    # 과학 해금
    science_unlocked: bool   # tech_level != primitive

    # 장착
    has_armor: bool

    # 자원 부족 (≤ 5개)
    grass_low: bool    # cutgrass ≤ 5
    twigs_low: bool    # twigs ≤ 5

    # 거미 전투 지표
    has_spider_drops: bool   # monstermeat / spidergland / silk 소유

    # 특수 아이템
    has_gold: bool           # goldnugget 1개 이상
    has_chester: bool        # chester_eyebone 소유

    # 기타
    in_cave: bool
    inventory_full: bool     # 본체 슬롯 15칸 모두 사용
    time_of_day: str         # day / dusk / night
    day: int
    day_bucket: str          # 1-5 / 6-10 / 11-15


def from_raw(raw: dict) -> GameState:
    world  = raw.get("world", {})
    vitals = raw.get("vitals", {})
    flags  = raw.get("flags", {})
    items  = raw.get("inventory", {}).get("items", [])
    tech   = raw.get("tech_level", "primitive")

    hp  = vitals.get("health",  {}).get("percent", 100)
    san = vitals.get("sanity",  {}).get("percent", 100)
    hun = vitals.get("hunger",  {}).get("percent", 100)

    spider_prefabs = {"monstermeat", "spidergland", "silk"}

    main_slots    = [it for it in items if isinstance(it.get("slot"), int)]

    day = world.get("day", 1)
    if day <= 5:    day_bucket = "1-5"
    elif day <= 10: day_bucket = "6-10"
    else:           day_bucket = "11-15"

    return GameState(
        health_level     = _level(hp),
        sanity_level     = _level(san),
        hunger_level     = _level(hun),
        science_unlocked = tech != "primitive",
        has_armor        = bool(flags.get("has_armor")),
        grass_low        = _count(items, "cutgrass") <= 5,
        twigs_low        = _count(items, "twigs") <= 5,
        has_spider_drops = _has_any(items, spider_prefabs),
        has_gold         = _count(items, "goldnugget") >= 1,
        has_chester      = _has_any(items, {"chester_eyebone"}),
        in_cave          = bool(world.get("is_cave")),
        inventory_full   = len(main_slots) >= 15,
        time_of_day      = world.get("time_of_day", "day"),
        day              = day,
        day_bucket       = day_bucket,
    )
