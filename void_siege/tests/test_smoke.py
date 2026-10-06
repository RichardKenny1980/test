"""Boots the real game headless and plays it with taps, the way a phone would."""
import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from void_siege.game import BattleScene, Game, MenuScene
from void_siege.settings import WIDTH


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def tap(pos):
    return [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1),
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)]


def option(scene, action, arg=None):
    return next(o for o in scene.ui.radial.options if o.action == action and (arg is None or o.arg == arg))


def button(scene, action):
    return next(b for b in scene.hud.buttons if b.action == (action,))


@pytest.fixture
def game():
    return Game(scaled=False)


def test_tap_to_deploy_build_upgrade_and_play(game):
    game.step(1 / 60)
    game.step(1 / 60, tap((100, 100)))  # tap anywhere on the title screen
    scene = game.scene
    assert isinstance(scene, BattleScene)
    world = scene.world

    # tap a pad: the ring menu opens; first tap on an option arms it, second builds
    game.step(1 / 60, tap(world.pads[3]))
    assert scene.ui.radial is not None and scene.ui.radial.pad == 3
    bunker = option(scene, "build", "bunker")
    game.step(1 / 60, tap((bunker.x, bunker.y)))
    assert 3 not in world.towers and scene.ui.radial.armed is bunker
    game.step(1 / 60, tap((bunker.x, bunker.y)))
    assert world.towers[3].kind == "bunker" and scene.ui.radial is None

    # tap the tower, then upgrade with two taps; aim applies on one tap
    game.step(1 / 60, tap(world.pads[3]))
    up = option(scene, "upgrade")
    game.step(1 / 60, tap((up.x, up.y)) + tap((up.x, up.y)))
    assert world.towers[3].tier == 1
    aim = option(scene, "target")
    game.step(1 / 60, tap((aim.x, aim.y)))
    assert world.towers[3].targeting == "last"

    # tapping empty ground closes the menu
    game.step(1 / 60, tap((330, 60)))
    assert scene.ui.radial is None

    # console buttons: launch the wave, speed up, pause
    game.step(1 / 60, tap(button(scene, "wave").rect.center))
    game.step(1 / 60, tap(button(scene, "speed").rect.center) + tap(button(scene, "speed").rect.center))
    assert world.waves.index == 0 and scene.ui.speed == 3
    for _ in range(600):
        game.step(1 / 60)
    assert world.kills > 0

    game.step(1 / 60, tap(button(scene, "pause").rect.center))
    assert scene.ui.paused
    t = world.time
    game.step(1 / 60)
    assert world.time == t
    resume = next(rect for rect, _ in scene.overlay_buttons)
    game.step(1 / 60, tap(resume.center))
    assert not scene.ui.paused


def test_cannot_build_without_minerals(game):
    game.start_battle()
    scene, world = game.scene, game.scene.world
    world.minerals = 10
    game.step(1 / 60, tap(world.pads[0]))
    mortar = option(scene, "build", "mortar")
    game.step(1 / 60, tap((mortar.x, mortar.y)) + tap((mortar.x, mortar.y)))
    assert 0 not in world.towers


def test_ring_menu_stays_on_screen_near_edges(game):
    game.start_battle()
    scene, world = game.scene, game.scene.world
    for pad in range(len(world.pads)):
        game.step(1 / 60, tap((330, 60)) + tap(world.pads[pad]))
        for opt in scene.ui.radial.options:
            assert 0 <= opt.x - 17 and opt.x + 17 <= WIDTH
            assert 0 <= opt.y - 17 and opt.y + 17 <= 280


def test_keyboard_shortcuts_still_work(game):
    game.start_battle()
    world = game.scene.world
    game.step(1 / 60, tap(world.pads[2]) + [key(pygame.K_3)])
    assert world.towers[2].kind == "cryo"


def test_game_over_buttons(game):
    game.start_battle()
    world = game.scene.world
    world.call_wave()
    world.core_hp = 1
    world.spawn("spine_brute", world.path.length - 0.1)
    for _ in range(90):
        game.step(1 / 60)
    assert world.lost
    retry, menu = (rect for rect, _ in game.scene.overlay_buttons)
    game.step(1 / 60, tap(retry.center))
    assert game.scene.world is not world and not game.scene.world.over
    game.scene.world.core_hp = 0
    for _ in range(60):
        game.step(1 / 60)
    menu = game.scene.overlay_buttons[1][0]
    game.step(1 / 60, tap(menu.center))
    assert isinstance(game.scene, MenuScene)
