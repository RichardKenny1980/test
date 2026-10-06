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
