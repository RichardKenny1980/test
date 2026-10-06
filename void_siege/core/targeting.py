import math


def choose_target(tower, enemies):
    """Pick the enemy this tower should shoot, using its targeting mode."""
    candidates = [e for e in enemies if tower.can_hit(e) and tower.in_range(e)]
    if not candidates:
        return None
    mode = tower.targeting
    if mode == "first":
        return max(candidates, key=lambda e: e.distance)
    if mode == "last":
        return min(candidates, key=lambda e: e.distance)
    if mode == "strongest":
        return max(candidates, key=lambda e: (e.hp, e.distance))
    if mode == "closest":
        return min(candidates, key=lambda e: math.hypot(e.x - tower.x, e.y - tower.y))
    raise ValueError(f"unknown targeting mode {mode!r}")
