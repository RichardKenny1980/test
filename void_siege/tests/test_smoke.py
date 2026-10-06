"""Boots the real game headless and plays through the menu into a battle."""
import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from void_siege.game import BattleScene, Game


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


def click(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def test_menu_to_battle_and_play():
    game = Game(scaled=False)
    game.step(1 / 60)
    game.step(1 / 60, [key(pygame.K_RETURN)])
    scene = game.scene
    assert isinstance(scene, BattleScene)
    world = scene.world

    # build a bunker with the hotkey and a click on pad 3, then select and upgrade it
    pad = world.pads[3]
    game.step(1 / 60, [key(pygame.K_1), pygame.event.Event(pygame.MOUSEMOTION, pos=pad, rel=(0, 0), buttons=(0, 0, 0))])
    game.step(1 / 60, [click(pad)])
    assert 3 in world.towers
    assert scene.ui.selected is world.towers[3]
    game.step(1 / 60, [key(pygame.K_u)])
    assert world.towers[3].tier == 1

    # command card: build a cryo tower via its button
    cryo_button = next(b for b in scene.hud.buttons if b.action == ("build", "cryo"))
    game.step(1 / 60, [click(cryo_button.rect.center), click(world.pads[1])])
    assert world.towers[1].kind == "cryo"

    game.step(1 / 60, [key(pygame.K_SPACE), key(pygame.K_f), key(pygame.K_f)])
    assert world.waves.index == 0 and scene.ui.speed == 3
    for _ in range(600):
        game.step(1 / 60)
    assert world.kills > 0

    game.step(1 / 60, [key(pygame.K_p)])
    assert scene.ui.paused
    t = world.time
    game.step(1 / 60)
    assert world.time == t


def test_game_over_screen_and_restart():
    game = Game(scaled=False)
    game.start_battle()
    world = game.scene.world
    world.call_wave()
    world.core_hp = 1
    world.spawn("spine_brute", world.path.length - 0.1)
    for _ in range(90):
        game.step(1 / 60)
    assert world.lost
    game.step(1 / 60, [key(pygame.K_r)])
    assert game.scene.world is not world and not game.scene.world.over
