"""Assemble the Android app project for buildozer / python-for-android.

    python -m void_siege.build_android
    cd build/android && buildozer android debug

The APK lands in build/android/bin/. CI does both steps (.github/workflows/void-siege-android.yml).
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "build" / "android"

MAIN = '''import asyncio

from void_siege.game import Game

asyncio.run(Game().run())
'''


def render_art(app):
    """Draw the launcher icon and splash screen from the game's own sprites."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from void_siege.render import palette as P
    from void_siege.render.art import SpriteBank, scale_by

    pygame.init()
    pygame.display.set_mode((1, 1))
    sprites = SpriteBank()

    icon = pygame.Surface((64, 64))
    icon.fill(P.GUNMETAL)
    pygame.draw.rect(icon, P.HAZARD, icon.get_rect(), 3)
    bunker = scale_by(sprites.icon("bunker", 2), 2)
    icon.blit(bunker, bunker.get_rect(center=(32, 32)))
    pygame.image.save(pygame.transform.scale(icon, (512, 512)), str(app / "icon.png"))

    splash = pygame.Surface((160, 90))
    splash.fill(P.BLACK)
    titan = scale_by(sprites.enemy("hive_titan", 0, 3.14159), 1.2)
    splash.blit(titan, titan.get_rect(center=(80, 36)))
    font = pygame.font.Font(None, 22)
    text = font.render("VOID SIEGE", False, P.HAZARD)
    splash.blit(text, text.get_rect(center=(80, 76)))
    pygame.image.save(pygame.transform.scale(splash, (1280, 720)), str(app / "presplash.png"))
    pygame.quit()


def assemble():
    APP.mkdir(parents=True, exist_ok=True)
    target = APP / "void_siege"
    if target.exists():
        shutil.rmtree(target)  # keep APP/.buildozer (the slow toolchain cache), refresh the game
    shutil.copytree(ROOT / "void_siege", target,
                    ignore=shutil.ignore_patterns("tests", "android", "__pycache__", "*.pyc", "build_*.py",
                                                  "README.md", "requirements.txt"))
    (APP / "main.py").write_text(MAIN, encoding="utf-8")
    shutil.copy(ROOT / "void_siege" / "android" / "buildozer.spec", APP / "buildozer.spec")
    render_art(APP)
    return APP


if __name__ == "__main__":
    print(f"Android project ready: {assemble()}")
