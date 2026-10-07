import os

MAP_WIDTH, MAP_HEIGHT = 640, 280  # the battlefield layout in data/*.json
FPS = 60
SPEEDS = (1, 2, 3)
TITLE = "Void Siege"
ANDROID = "ANDROID_ARGUMENT" in os.environ  # set by python-for-android's launcher
DEFAULT_ASPECT = 20 / 9           # a typical phone held sideways


def _aspect():
    forced = os.environ.get("VOID_SIEGE_ASPECT")
    if forced:
        return float(forced)
    if not ANDROID:
        return DEFAULT_ASPECT
    import pygame

    pygame.display.init()
    info = pygame.display.Info()
    long_side, short_side = max(info.current_w, info.current_h), min(info.current_w, info.current_h)
    return long_side / short_side if short_side > 0 else DEFAULT_ASPECT


def _canvas(aspect):
    """The smallest canvas with the screen's shape that still holds the whole map.

    The battlefield is the whole screen (no console panel), so the smaller this canvas is,
    the bigger everything looks once it is scaled up to the phone. Leftover space on a
    taller or wider screen becomes extra terrain around the centred map.
    """
    aspect = min(max(aspect, 4 / 3), 3.0)
    width = max(MAP_WIDTH, round(MAP_HEIGHT * aspect))
    height = max(MAP_HEIGHT, round(width / aspect))
    return width + width % 2, height + height % 2


WIDTH, HEIGHT = _canvas(_aspect())
FIELD_HEIGHT = HEIGHT             # the battlefield fills the canvas
FIELD_X = (WIDTH - MAP_WIDTH) // 2
FIELD_Y = (HEIGHT - MAP_HEIGHT) // 2
