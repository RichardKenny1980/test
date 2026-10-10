"""A simple scripted player used to sanity-check balance in tests."""
from void_siege.core.world import World

# (wave number to have it by, tower kind, pad index)
BUILD_ORDER = [
    (1, "bunker", 3), (1, "bunker", 1), (2, "bunker", 6), (2, "mortar", 4),
    (3, "cryo", 2), (4, "missile", 7), (4, "bunker", 8), (5, "missile", 11),
    (6, "mortar", 10), (6, "bunker", 5), (7, "cryo", 12), (8, "missile", 9),
    (8, "mortar", 0), (9, "bunker", 13),
]


def play(world=None, build_order=BUILD_ORDER, upgrade=True, max_seconds=1200):
    world = world or World()
    pending = list(build_order)
    while not world.over and world.time < max_seconds:
        wave = world.waves.index + 1
        while pending and pending[0][0] <= wave + 1 and world.minerals >= world.build_cost(pending[0][1]):
            _, kind, pad = pending.pop(0)
            world.build(kind, pad)
        if upgrade and not pending:
            for tower in sorted(world.towers.values(), key=lambda t: t.tier):
                cost = tower.upgrade_cost
                if cost is not None and world.minerals >= cost:
                    world.upgrade(tower)
        if world.waves.index < 0:
            world.call_wave()
        world.update()
        world.drain_events()
    return world


KIND_PLAN = ("bunker", "bunker", "mortar", "cryo", "missile", "mortar", "bunker", "missile", "cryo", "mortar")


def _coverage(world, x, y, reach, step=8):
    path = world.path
    points = (path.position(d) for d in range(0, int(path.length), step))
    return sum(1 for px, py, _ in points if (px - x) ** 2 + (py - y) ** 2 <= reach * reach)


def best_spot(world, kind):
    """Free pad or cell where a turret of `kind` covers the most road. On maze levels a spot that
    makes the Hive's route longer scores extra, so the bot builds a maze as it goes."""
    reach = world.tower_specs[kind]["tiers"][0]["range"]
    best, best_score = None, 0
    base_len = world.path.length
    for pad, (x, y) in enumerate(world.pads):
        if pad in world.towers:
            continue
        score = _coverage(world, x, y, reach)
        if world.kind == "maze" and score:
            if world.blocks_route(pad):
                continue
            g = world.grid
            dist = g.distances(world.core_cell, world.walls | {world.pad_cells[pad]})
            score += (dist[world.entry] * 20 - base_len) / 8 * 0.6
        if score > best_score:
            best, best_score = pad, score
    return best


def smart_play(world, max_towers=99, max_seconds=1500):
    """A sensible player for any level: builds a mixed defence where it covers the most road, and
    alternates new turrets with upgrades. Used to check every level can be won."""
    plan = upgrades = 0
    next_think = 0.0
    while not world.over and world.time < max_seconds:
        if world.time >= next_think:
            next_think = world.time + 0.5
            kind = KIND_PLAN[plan % len(KIND_PLAN)]
            upgradable = sorted((t for t in world.towers.values() if t.upgrade_cost is not None),
                                key=lambda t: (t.tier, t.upgrade_cost))
            build = len(world.towers) < max_towers and (len(world.towers) < 6 or upgrades >= len(world.towers) - 6)
            can_pay = world.minerals >= world.build_cost(kind)
            pad = best_spot(world, kind) if build and can_pay else None
            if build and not can_pay:
                pass  # save up for the next turret
            elif pad is not None:
                if world.build(kind, pad):
                    plan += 1
            elif upgradable and world.minerals >= upgradable[0].upgrade_cost:
                world.upgrade(upgradable[0])
                upgrades += 1
        if world.waves.index < 0 and len(world.towers) >= min(2, max_towers):
            world.call_wave()
        world.update()
        world.drain_events()
    return world
