import pytest

from void_siege.core.path import Path
from void_siege.core.targeting import choose_target
from void_siege.core.world import TICK, World
from void_siege.tests.autoplay import play


def run(world, seconds):
    for _ in range(int(seconds / TICK)):
        world.update()


def test_path_position_and_length():
    path = Path([(0, 0), (10, 0), (10, 10)])
    assert path.length == 20
    assert path.position(5)[:2] == (5, 0)
    assert path.position(15)[:2] == (10, 5)
    assert path.position(99)[:2] == (10, 10)


def test_pads_stay_clear_of_the_road():
    world = World()
    for x, y in world.pads:
        assert world.path.distance_to(x, y) >= 28, (x, y)
        assert 12 <= y <= 268


def test_build_upgrade_and_sell_economy():
    world = World()
    start = world.minerals
    tower = world.build("bunker", 0)
    assert world.minerals == start - 60
    assert world.build("bunker", 0) is None  # pad taken
    assert world.upgrade(tower)
    assert tower.tier == 1 and world.minerals == start - 130
    world.sell(tower)
    assert world.minerals == start - 130 + int(130 * 0.7)
    assert 0 not in world.towers


def test_cannot_build_without_minerals():
    world = World()
    world.minerals = 10
    assert world.build("mortar", 0) is None


def test_targeting_modes():
    world = World()
    tower = world.build("bunker", 3)  # (150, 120), next to the first vertical stretch
    back, front = world.spawn("skitterling", 150), world.spawn("skitterling", 170)
    tank = world.spawn("spine_brute", 140)
    tower.targeting = "first"
    assert choose_target(tower, world.enemies) is front
    tower.targeting = "last"
    assert choose_target(tower, world.enemies) is tank
    tower.targeting = "strongest"
    assert choose_target(tower, world.enemies) is tank
    tower.cycle_targeting()
    assert tower.targeting == "closest"
    assert back in world.enemies


def test_armor_reduces_damage_unless_piercing():
    world = World()
    crawler = world.spawn("carapace_crawler")
    assert crawler.take_damage(10) == 4
    assert crawler.take_damage(10, pierce=True) == 10
    assert crawler.take_damage(4) == 1  # armor never cuts below 25%


def test_slow_and_boss_resistance():
    world = World()
    bug, titan = world.spawn("skitterling"), world.spawn("hive_titan")
    bug.apply_slow(0.5, 1.0)
    titan.apply_slow(0.5, 1.0)
    assert bug.speed == pytest.approx(55 * 0.5)
    assert titan.speed == pytest.approx(12 * 0.75)
    bug.update(1.1)
    assert bug.slow == 0


def test_ground_towers_ignore_fliers_and_burrowers_need_detection():
    world = World()
    mortar = world.build("mortar", 3)
    flier = world.spawn("gloomwing", 100)
    assert not mortar.can_hit(flier)
    world.enemies.remove(flier)
    bunker = world.build("bunker", 1)
    burrower = world.spawn("burrower", 140)
    world.update()
    assert not burrower.targetable and not bunker.can_hit(burrower)
    world.minerals = 500
    world.build("missile", 2)  # (70, 170) detector covers the first corner
    world.update()
    assert burrower.detected and bunker.can_hit(burrower)


def test_leaks_cost_core_hp_and_end_the_game():
    world = World()
    world.call_wave()
    run(world, 25)
    assert 0 < world.core_hp < world.max_core_hp
    world.core_hp = 1
    world.spawn("spine_brute", world.path.length - 0.1)
    world.update()
    assert world.lost and world.over


def test_calling_early_pays_bonus():
    world = World()
    world.call_wave()
    run(world, 10)  # wave 1 finishes spawning after ~8s
    assert world.waves.countdown is not None
    before = world.minerals
    bonus = world.call_wave()
    assert bonus >= world.map["wave_bonus"]
    assert world.minerals == before + bonus
    assert world.waves.index == 1


def test_next_wave_auto_starts_after_gap():
    world = World()
    world.call_wave()
    run(world, 9 + world.map["wave_gap"] + 1)
    assert world.waves.index == 1


def test_titan_spawns_broodlings():
    world = World()
    world.spawn("hive_titan")
    run(world, 4.1)
    assert sum(e.kind == "skitterling" for e in world.enemies) == 1


def test_good_play_wins_with_three_stars():
    world = play()
    assert world.won and world.stars == 3


def test_doing_nothing_loses_early():
    world = play(build_order=[])
    assert world.lost and world.waves.index <= 2


def test_counters_matter_bunker_spam_loses():
    pads = [3, 1, 6, 4, 2, 7, 8, 11, 10, 5, 12, 9, 0, 13]
    world = play(build_order=[(i // 2 + 1, "bunker", p) for i, p in enumerate(pads)])
    assert world.lost


def test_shifted_map_keeps_spawn_at_screen_edge_and_is_still_winnable():
    from void_siege.tests.autoplay import play

    world = World(offset_x=80)
    base = World()
    assert world.path.points[0] == base.path.points[0]  # enemies still walk in from the left edge
    assert world.pads[0] == (base.pads[0][0] + 80, base.pads[0][1])
    assert world.core == (base.core[0] + 80, base.core[1])
    play(world)
    assert world.won
