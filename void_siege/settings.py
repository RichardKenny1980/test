import os

BASE_WIDTH, HEIGHT = 640, 360     # low-res render target, scaled up to the window
FIELD_HEIGHT = 280                # playfield above the console panel
FPS = 60
SPEEDS = (1, 2, 3)
TITLE = "Void Siege"
ANDROID = "ANDROID_ARGUMENT" in os.environ  # set by python-for-android's launcher


def _screen_width():
    """Widen the canvas to the phone's shape so the game fills the screen instead of being letterboxed.

    The canvas is always HEIGHT pixels tall; a 20:9 phone gets a canvas about 800 wide. The map keeps
    its 640-wide layout and is centred (FIELD_X), with extra terrain painted either side.
    """
    forced = os.environ.get("VOID_SIEGE_WIDTH")
    if forced:
        return max(BASE_WIDTH, int(forced))
    if not ANDROID:
        return BASE_WIDTH
    import pygame

    pygame.display.init()
    info = pygame.display.Info()
    long_side, short_side = max(info.current_w, info.current_h), min(info.current_w, info.current_h)
    if short_side <= 0:
        return BASE_WIDTH
    width = round(HEIGHT * long_side / short_side / 2) * 2
    return min(max(width, BASE_WIDTH), 900)


WIDTH = _screen_width()
FIELD_X = (WIDTH - BASE_WIDTH) // 2
