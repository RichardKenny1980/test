"""Window, main loop and scenes (title menu and battle).

One control scheme for phones and desktops: every action is a tap (or click).
Keyboard shortcuts exist as extras on desktop.
"""
import asyncio
import math
import random
import sys

import pygame

from .core import levels
from .core.grid import CELL
from .core.world import TICK, World
from .render import palette as P
from .render.art import SpriteBank
from .render.field import FieldRenderer
from .render.fx import Effects
from .render.hud import TOP_BAR, Hud, make_buttons
from .render.radial import BUILD_ORDER, RadialMenu
from .settings import ANDROID, FIELD_HEIGHT, FIELD_X, FIELD_Y, FPS, HEIGHT, SPEEDS, TITLE, WIDTH

WEB = sys.platform == "emscripten"
BUILD_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
PAD_TAP_RADIUS = 16
THREAT_TIPS = {
    "gloomwing": ("Gloomwings incoming! They fly over the road.",
                  "Mortars can't hit flyers. Use Bunkers, Cryo or Missiles."),
    "burrower": ("Burrowers! They tunnel underground and can't be targeted.",
                 "A Missile Battery's radar reveals them so every turret can fire."),
}
BACK_KEYS = (pygame.K_ESCAPE, pygame.K_AC_BACK)  # Esc on desktop, the Back button on Android
BLOCKED_SAYS = {
    "sealed": "Can't build there. It would seal the Hive's path, and they must have a way through.",
    "occupied": "Can't build on top of the bugs. Wait for them to move.",
}
BUILD_HINTS = {
    "pads": "Tap a build pad for a turret. Tap WAVE when ready.",
    "open": "Tap any open ground beside the road for a turret. Tap WAVE when ready.",
    "maze": "Your turrets are the walls. Tap any ground to build. Tap WAVE when ready.",
}


def outlined_text(font, text, color, outline=P.BLACK):
    base = font.render(text, False, color)
    s = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
    shadow = font.render(text, False, outline)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (2, 2)):
        s.blit(shadow, (dx, dy))
    s.blit(base, (1, 1))
    return s


def is_portrait():
    """True when a phone browser is held upright. The battlefield needs landscape."""
    if not WEB:
        return False
    try:
        import platform

        return platform.window.innerHeight > platform.window.innerWidth
    except (AttributeError, ImportError):
        return False


class Game:
    def __init__(self, scaled=not WEB):
        pygame.init()
        pygame.display.set_caption(TITLE)
        flags = pygame.SCALED if scaled else 0
        if ANDROID:
            flags |= pygame.FULLSCREEN  # immersive: hides the status and navigation bars
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        self.clock = pygame.time.Clock()
        self.fonts = {
            "small": pygame.font.Font(None, 15),
            "normal": pygame.font.Font(None, 20),
            "big": pygame.font.Font(None, 30),
            "title": pygame.font.Font(None, 72),
        }
        self.sprites = SpriteBank()
        self.progress = levels.Progress()
        self.level = 0
        self.running = True
        self.portrait = False
        self._orientation_check = 0
        self.scene = MenuScene(self)

    def start_battle(self, level=None):
        if level is not None:
            self.level = level
        self.scene = BattleScene(self, self.level)

    def to_menu(self):
        self.scene = MenuScene(self)

    def to_levels(self):
        self.scene = LevelSelectScene(self)

    def step(self, dt, events=()):
        self._orientation_check -= 1
        if self._orientation_check <= 0:
            self.portrait = is_portrait()
            self._orientation_check = 30
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif not self.portrait:
                self.scene.handle(event)
        if self.portrait:
            self._rotate_hint()
            return
        self.scene.update(dt)
        self.scene.draw(self.screen)

    def _rotate_hint(self):
        screen = self.screen
        screen.fill(P.BLACK)
        cx, cy = WIDTH // 2, HEIGHT // 2 - 30
        phone = pygame.Rect(0, 0, 40, 70)
        phone.center = (cx, cy)
        pygame.draw.rect(screen, P.STEEL, phone, 3, border_radius=6)
        pygame.draw.arc(screen, P.HAZARD, phone.inflate(50, 30), 0.3, 1.4, 3)
        msg = outlined_text(self.fonts["big"], "Rotate your device", P.HAZARD)
        screen.blit(msg, msg.get_rect(center=(cx, cy + 70)))

    async def run(self):
        """Main loop. It is async so the same code runs in a phone browser (pygbag) and on desktop."""
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)
            self.step(dt, pygame.event.get())
            pygame.display.flip()
            await asyncio.sleep(0)
        pygame.quit()


class MenuScene:
    def __init__(self, game):
        self.game = game
        rng = random.Random(1)
        self.stars = [[rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT), rng.choice((6, 12, 24)),
                       rng.choice((P.WHITE, P.TEAM_BLUE_LIGHT, P.STEEL_LIGHT, P.HAZARD))] for _ in range(160)]
        self.time = 0.0
        self.button = pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 + 30, 160, 44)
        self.mouse = (0, 0)
        self.sprites = game.sprites

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.game.to_levels()  # tap anywhere to deploy
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.game.to_levels()
            elif event.key in BACK_KEYS:
                self.game.running = False

    def update(self, dt):
        self.time += dt
        for s in self.stars:
            s[0] -= s[2] * dt
            if s[0] < 0:
                s[0] += WIDTH

    def draw(self, screen):
        f = self.game.fonts
        screen.fill(P.BLACK)
        for x, y, speed, color in self.stars:
            screen.set_at((int(x), int(y)), color if speed > 6 else P.STEEL_DARK)
        # the frontier moon
        cx, cy = WIDTH - 140, HEIGHT - 40
        pygame.draw.circle(screen, P.SAND_DARK, (cx, cy), 150)
        pygame.draw.circle(screen, P.SAND, (cx - 10, cy - 10), 140)
        for ox, oy, r in ((-60, -90, 18), (20, -110, 10), (-110, -30, 12), (40, -60, 24)):
            pygame.draw.circle(screen, P.SAND_DARK, (cx + ox, cy + oy), r)
            pygame.draw.circle(screen, P.ROCK, (cx + ox + 2, cy + oy + 2), r - 3)
        pygame.draw.circle(screen, P.CREEP, (cx - 120, cy - 100), 30)
        pygame.draw.circle(screen, P.CREEP_DARK, (cx - 115, cy - 95), 16)
        # a few hive critters crawling across the title
        for i, kind in enumerate(("skitterling", "skitterling", "spine_brute", "gloomwing")):
            x = (self.time * 30 + i * 70) % (WIDTH + 80) - 40
            y = HEIGHT // 2 + (i % 2) * 10 if kind != "gloomwing" else HEIGHT // 2 - 30 + math.sin(self.time * 2) * 6
            img = self.sprites.enemy(kind, self.time, 0)
            screen.blit(img, img.get_rect(center=(int(x), int(y))))

        title = outlined_text(f["title"], "VOID SIEGE", P.HAZARD, P.RUST)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))
        sub = outlined_text(f["normal"], "Hold the frontier against the Skrell Hive", P.TEAM_BLUE_LIGHT)
        screen.blit(sub, sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 42)))

        hover = self.button.collidepoint(self.mouse)
        pygame.draw.rect(screen, P.HAZARD if hover else P.STEEL_DARK, self.button)
        pygame.draw.rect(screen, P.GUNMETAL, self.button.inflate(-4, -4))
        label = outlined_text(f["big"], "DEPLOY", P.CRT_GREEN)
        screen.blit(label, label.get_rect(center=self.button.center))

        help_lines = [
            "Tap where you want a turret.  Tap a turret to upgrade, sell or aim.",
            "Tap once to see details, tap again to confirm.",
        ]
        for i, line in enumerate(help_lines):
            img = outlined_text(f["small"], line, P.STEEL_LIGHT)
            screen.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 34 + i * 14)))


class LevelSelectScene:
    """Pick a sector. Cards show the level's style and best stars; clearing a level opens the next."""

    COLS = 3
    CARD_W, CARD_H = 180, 70

    def __init__(self, game):
        self.game = game
        self.levels = [levels.info(i) for i in range(len(levels.LEVELS))]
        self.cards = []
        rows = (len(self.levels) + self.COLS - 1) // self.COLS
        gap = 12
        top = (HEIGHT - rows * self.CARD_H - (rows - 1) * gap) // 2 + 14
        left = (WIDTH - self.COLS * self.CARD_W - (self.COLS - 1) * gap) // 2
        for i in range(len(self.levels)):
            r, c = divmod(i, self.COLS)
            self.cards.append(pygame.Rect(left + c * (self.CARD_W + gap), top + r * (self.CARD_H + gap),
                                          self.CARD_W, self.CARD_H))
        self.back = pygame.Rect(6, 6, 64, 30)
        self.message, self.message_time = "", 0.0
        self.time = 0.0

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.tap(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key in BACK_KEYS:
                self.game.to_menu()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.game.start_battle(self.newest())

    def newest(self):
        """The furthest level the player can play."""
        return max(i for i in range(len(self.levels)) if self.game.progress.unlocked(i))

    def tap(self, pos):
        if self.back.collidepoint(pos):
            self.game.to_menu()
            return
        for i, rect in enumerate(self.cards):
            if rect.collidepoint(pos):
                if self.game.progress.unlocked(i):
                    self.game.start_battle(i)
                else:
                    self.message, self.message_time = f"Clear sector {i} to unlock this one.", 2.5
                return

    def update(self, dt):
        self.time += dt
        self.message_time = max(0.0, self.message_time - dt)

    def draw(self, screen):
        f, progress = self.game.fonts, self.game.progress
        screen.fill(P.BLACK)
        for i in range(90):  # a quiet star field
            x = (i * 97 + int(self.time * (6 + i % 3 * 6))) % WIDTH
            screen.set_at((x, (i * 53) % HEIGHT), P.STEEL_LIGHT if i % 3 else P.STEEL_DARK)
        title = outlined_text(f["big"], "SELECT SECTOR", P.HAZARD, P.RUST)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 20)))
        for i, (lv, rect) in enumerate(zip(self.levels, self.cards)):
            open_ = progress.unlocked(i)
            stars = progress.best(i)
            pygame.draw.rect(screen, P.HAZARD if open_ and stars == 0 and i == self.newest() else P.STEEL_DARK, rect)
            pygame.draw.rect(screen, P.GUNMETAL if open_ else (24, 26, 30), rect.inflate(-4, -4))
            color = P.CRT_GREEN if open_ else P.STEEL_DARK
            num = outlined_text(f["big"], str(i + 1), P.HAZARD if open_ else P.STEEL_DARK)
            screen.blit(num, (rect.x + 8, rect.y + 6))
            name = outlined_text(f["normal"], lv["name"].upper(), color)
            screen.blit(name, (rect.x + 30, rect.y + 8))
            kind = outlined_text(f["small"], levels.KIND_LABELS[lv["kind"]], P.TEAM_BLUE_LIGHT if open_ else P.STEEL_DARK)
            screen.blit(kind, (rect.x + 30, rect.y + 28))
            waves = outlined_text(f["small"], f"{lv['waves']} WAVES", P.STEEL_LIGHT if open_ else P.STEEL_DARK)
            screen.blit(waves, waves.get_rect(topright=(rect.right - 8, rect.y + 47)))
            if open_:
                for s in range(3):
                    draw_star(screen, rect.x + 40 + s * 22, rect.y + 52, s < stars, 8)
            else:
                lock = pygame.Rect(0, 0, 14, 11)
                lock.center = (rect.x + 48, rect.y + 54)
                pygame.draw.arc(screen, P.STEEL, lock.move(0, -8).inflate(-4, 4), 0, math.pi, 2)
                pygame.draw.rect(screen, P.STEEL, lock)
                img = outlined_text(f["small"], "LOCKED", P.STEEL_DARK)
                screen.blit(img, (rect.x + 64, rect.y + 49))
        pygame.draw.rect(screen, P.STEEL_DARK, self.back)
        pygame.draw.rect(screen, P.GUNMETAL, self.back.inflate(-4, -4))
        img = outlined_text(f["normal"], "BACK", P.CRT_GREEN)
        screen.blit(img, img.get_rect(center=self.back.center))
        if self.message_time > 0:
            img = outlined_text(f["normal"], self.message, P.HAZARD)
            screen.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT - 14)))


def draw_star(screen, x, y, filled, size=10):
    pts = []
    for i in range(10):
        r = size if i % 2 == 0 else size * 0.4
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
    pygame.draw.polygon(screen, P.HAZARD if filled else P.STEEL_DARK, pts)
    pygame.draw.polygon(screen, P.BLACK, pts, 1)


class UiState:
    def __init__(self):
        self.radial = None    # ring menu open around a pad, if any
        self.pressed = None   # control button under the finger, for press feedback
        self.mouse = (0, 0)
        self.speed = 1
        self.paused = False

    @property
    def selected(self):
        return self.radial.tower if self.radial else None

    @property
    def preview_kind(self):
        armed = self.radial.armed if self.radial else None
        return armed.arg if armed is not None and armed.action == "build" else None


class BattleScene:
    def __init__(self, game, level=0):
        self.game = game
        self.level = level
        reserved = [b.rect for b in make_buttons()] + [TOP_BAR]  # no turrets hidden under the HUD
        self.world = World(levels.LEVELS[level], offset_x=FIELD_X, offset_y=FIELD_Y, reserved=reserved)
        self.ui = UiState()
        self.field = FieldRenderer(self.world, game.sprites)
        self.fx = Effects(game.fonts["small"])
        self.hud = Hud((game.fonts["normal"], game.fonts["small"]), game.sprites, self.field)
        self.accumulator = 0.0
        self.over_time = 0.0
        self.recorded = False
        self.overlay_buttons = []
        self.warned = set()
        for line in self.world.map.get("intro", ["Commander, the Hive is moving on the colony."]):
            self.fx.say(line, seconds=6.0)
        self.fx.say(BUILD_HINTS[self.world.kind], seconds=6.0)

    # ---- input ------------------------------------------------------------------

    def handle(self, event):
        ui = self.ui
        if event.type == pygame.MOUSEMOTION:
            ui.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONUP:
            ui.pressed = None
        elif event.type == pygame.KEYDOWN:
            self._key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            ui.mouse = event.pos
            if event.button == 1:
                self.tap(event.pos)
            elif event.button == 3:
                ui.radial = None

    def tap(self, pos):
        """Everything the player does goes through here: one tap (or click) at a screen position."""
        w, ui = self.world, self.ui
        for rect, action in self.overlay_buttons:
            if rect.collidepoint(pos):
                action()
                return
        if w.over:
            return
        if ui.radial is not None and not ui.paused:  # an open ring sits above the corner buttons
            opt = ui.radial.option_at(pos)
            if opt is not None:
                self.choose(opt)
                return
        button = self.hud.button_at(pos)
        if button:
            ui.pressed = button
            self.do(*button.action)
            return
        if ui.paused:
            return
        ui.radial = None
        pad = self._pad_near(pos)
        blocked = pad is not None and w.blocks_route(pad)
        if blocked:
            self.fx.say(BLOCKED_SAYS[blocked])
        elif pad is not None:
            ui.radial = RadialMenu(w, pad)

    def _pad_near(self, pos):
        w = self.world
        if w.grid is not None:  # open and maze levels: the cell under the finger
            g, (x, y) = w.grid, pos
            if not (g.ox <= x < g.ox + g.cols * CELL and g.oy <= y < g.oy + g.rows * CELL):
                return None
            return w.cell_pad.get(g.cell_at(x, y))
        best, best_d = None, PAD_TAP_RADIUS
        for i, (px, py) in enumerate(self.world.pads):
            d = math.hypot(pos[0] - px, pos[1] - py)
            if d <= best_d:
                best, best_d = i, d
        return best

    def choose(self, opt):
        """First tap on a ring option arms it (shows details); the second tap confirms."""
        radial = self.ui.radial
        if opt.confirm and radial.armed is not opt:
            radial.armed = opt
            return
        if not radial.affordable(opt):
            self.fx.say("Not enough minerals.")
            return
        w = self.world
        if opt.action == "build":
            blocked = w.blocks_route(radial.pad)  # the maze may have changed since the ring opened
            if blocked:
                self.fx.say(BLOCKED_SAYS[blocked])
            else:
                w.build(opt.arg, radial.pad)
            self.ui.radial = None
        elif opt.action == "upgrade":
            w.upgrade(radial.tower)
            self.ui.radial = RadialMenu(w, radial.pad)
        elif opt.action == "sell":
            w.sell(radial.tower)
            self.ui.radial = None
        elif opt.action == "target":
            radial.tower.cycle_targeting()

    def _confirm(self, action, arg=None):
        """Keyboard shortcut: run a ring option immediately, skipping the confirm tap."""
        radial = self.ui.radial
        if radial is None:
            return
        for opt in radial.options:
            if opt.action == action and (arg is None or opt.arg == arg):
                radial.armed = opt
                self.choose(opt)
                return

    def _key(self, event):
        w, ui, key = self.world, self.ui, event.key
        if w.over:
            if key == pygame.K_r:
                self.game.start_battle()
            elif key == pygame.K_n and self._has_next():
                self._next()
            elif key in (*BACK_KEYS, pygame.K_m, pygame.K_RETURN):
                self.game.to_levels()
            return
        if ui.paused and key == pygame.K_q:
            self.game.to_levels()
        elif key in BUILD_KEYS:
            self._confirm("build", BUILD_ORDER[BUILD_KEYS[key]])
        elif key == pygame.K_u:
            self._confirm("upgrade")
        elif key == pygame.K_s:
            self._confirm("sell")
        elif key == pygame.K_t:
            self._confirm("target")
        elif key == pygame.K_f:
            self.do("speed")
        elif key == pygame.K_SPACE:
            self.do("wave")
        elif key == pygame.K_p:
            self.do("pause")
        elif key in BACK_KEYS:
            if ui.radial:
                ui.radial = None
            else:
                self.do("pause")

    def do(self, action):
        w, ui = self.world, self.ui
        if action == "speed":
            ui.speed = SPEEDS[(SPEEDS.index(ui.speed) + 1) % len(SPEEDS)]
        elif action == "pause":
            ui.paused = not ui.paused
        elif action == "wave":
            w.call_wave()

    # ---- update & draw --------------------------------------------------------------

    def update(self, dt):
        w, ui = self.world, self.ui
        if ui.radial is not None and ui.radial.tower is not None and ui.radial.pad not in w.towers:
            ui.radial = None
        if not ui.paused and not w.over:
            self.accumulator += dt * ui.speed
            ticks = 0
            while self.accumulator >= TICK and ticks < 12:
                w.update(TICK)
                self.accumulator -= TICK
                ticks += 1
            self.accumulator = min(self.accumulator, TICK)
            self.field.time += dt
            self.fx.update(dt * ui.speed)
        elif w.over:
            if not self.recorded:
                self.recorded = True
                self.game.progress.record(self.level, w.stars)
            self.over_time += dt
            self.fx.update(dt)
            ui.radial = None
        for name, data in w.drain_events():
            self.fx.handle(name, data, self.field.ground, self.field.rng, self.field.splat)
        self._warn_new_threats()
        self.fx.update_chatter(dt)

    def _warn_new_threats(self):
        """The first time a flyer or a burrower shows up, tell the player which turrets can deal with it."""
        for e in self.world.enemies:
            kind = e.kind
            if kind in THREAT_TIPS and kind not in self.warned:
                self.warned.add(kind)
                for line in THREAT_TIPS[kind]:
                    self.fx.say(line, seconds=7.0)  # long enough to read mid-fight

    def draw(self, screen):
        screen.fill(P.BLACK)
        field = self.field.draw(self.fx, self.ui, self.game.fonts["small"])
        ox, oy = self.fx.shake_offset()
        screen.blit(field, (ox, oy))
        self.hud.draw(screen, self.world, self.ui, 1 / FPS)
        self.hud.draw_chatter(screen, self.fx)
        self.overlay_buttons = []
        if self.ui.paused and not self.world.over:
            self._overlay(screen, "PAUSED", "The Hive waits for no one.", P.HAZARD,
                          buttons=[("RESUME", lambda: self.do("pause")), ("QUIT", self.game.to_levels)])
        if self.world.over and self.over_time > 0.6:
            buttons = [("RETRY", self.game.start_battle), ("LEVELS", self.game.to_levels)]
            if self.world.won:
                if self._has_next():
                    buttons.insert(0, ("NEXT", self._next))
                self._overlay(screen, "VICTORY", f"{self.world.map['name']} holds.  Kills: {self.world.kills}",
                              P.CRT_GREEN, stars=self.world.stars, buttons=buttons)
            else:
                self._overlay(screen, "CORE DESTROYED", f"The Hive overran the colony on wave "
                                                        f"{self.world.waves.index + 1}.", P.RED, buttons=buttons)

    def _has_next(self):
        return self.level + 1 < len(levels.LEVELS)

    def _next(self):
        self.game.start_battle(self.level + 1)

    def _overlay(self, screen, title, subtitle, color, stars=None, buttons=()):
        f = self.game.fonts
        dim = pygame.Surface((WIDTH, FIELD_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        screen.blit(dim, (0, 0))
        box = pygame.Rect(0, 0, 300, 150 if stars is not None else 126)
        box.center = (WIDTH // 2, FIELD_HEIGHT // 2)
        pygame.draw.rect(screen, P.STEEL_DARK, box)
        pygame.draw.rect(screen, P.BLACK, box.inflate(-6, -6))
        pygame.draw.rect(screen, color, box.inflate(-6, -6), 1)
        t = outlined_text(f["big"], title, color)
        screen.blit(t, t.get_rect(center=(box.centerx, box.y + 22)))
        s = outlined_text(f["small"], subtitle, P.WHITE)
        screen.blit(s, s.get_rect(center=(box.centerx, box.y + 44)))
        y = box.y + 70
        if stars is not None:
            for i in range(3):
                draw_star(screen, box.centerx - 30 + i * 30, y, i < stars)
            y += 24
        width = 110 if len(buttons) < 3 else 88
        for i, (label, action) in enumerate(buttons):
            rect = pygame.Rect(0, 0, width, 36)
            rect.center = (box.centerx + (i - (len(buttons) - 1) / 2) * (width + 8), y + 16)
            pygame.draw.rect(screen, P.STEEL_DARK, rect)
            pygame.draw.rect(screen, P.GUNMETAL, rect.inflate(-4, -4))
            img = outlined_text(f["normal"], label, P.CRT_GREEN)
            screen.blit(img, img.get_rect(center=rect.center))
            self.overlay_buttons.append((rect, action))


def main():
    asyncio.run(Game().run())
