"""Window, main loop and scenes (title menu and battle)."""
import math
import random

import pygame

from .core.world import TICK, World
from .render import palette as P
from .render.art import SpriteBank
from .render.field import FieldRenderer
from .render.fx import Effects
from .render.hud import Hud
from .settings import FIELD_HEIGHT, FPS, HEIGHT, SPEEDS, TITLE, WIDTH

BUILD_KEYS = {pygame.K_1: "bunker", pygame.K_2: "mortar", pygame.K_3: "cryo", pygame.K_4: "missile"}


def outlined_text(font, text, color, outline=P.BLACK):
    base = font.render(text, False, color)
    s = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
    shadow = font.render(text, False, outline)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (2, 2)):
        s.blit(shadow, (dx, dy))
    s.blit(base, (1, 1))
    return s


class Game:
    def __init__(self, scaled=True):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED if scaled else 0)
        self.clock = pygame.time.Clock()
        self.fonts = {
            "small": pygame.font.Font(None, 15),
            "normal": pygame.font.Font(None, 20),
            "big": pygame.font.Font(None, 30),
            "title": pygame.font.Font(None, 72),
        }
        self.sprites = SpriteBank()
        self.running = True
        self.scene = MenuScene(self)

    def start_battle(self):
        self.scene = BattleScene(self)

    def to_menu(self):
        self.scene = MenuScene(self)

    def step(self, dt, events=()):
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            else:
                self.scene.handle(event)
        self.scene.update(dt)
        self.scene.draw(self.screen)

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)
            self.step(dt, pygame.event.get())
            pygame.display.flip()
        pygame.quit()


class MenuScene:
    def __init__(self, game):
        self.game = game
        rng = random.Random(1)
        self.stars = [[rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT), rng.choice((6, 12, 24)),
                       rng.choice((P.WHITE, P.TEAM_BLUE_LIGHT, P.STEEL_LIGHT, P.HAZARD))] for _ in range(160)]
        self.time = 0.0
        self.button = pygame.Rect(WIDTH // 2 - 60, 220, 120, 26)
        self.mouse = (0, 0)
        self.sprites = game.sprites

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.button.collidepoint(event.pos):
            self.game.start_battle()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.game.start_battle()
            elif event.key == pygame.K_ESCAPE:
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
        cx, cy = 500, 300
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
            y = 180 + (i % 2) * 10 if kind != "gloomwing" else 150 + math.sin(self.time * 2) * 6
            img = self.sprites.enemy(kind, self.time, 0)
            screen.blit(img, img.get_rect(center=(int(x), int(y))))

        title = outlined_text(f["title"], "VOID SIEGE", P.HAZARD, P.RUST)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 80)))
        sub = outlined_text(f["normal"], "Hold Dustfall Ridge against the Skrell Hive", P.TEAM_BLUE_LIGHT)
        screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 118)))

        hover = self.button.collidepoint(self.mouse)
        pygame.draw.rect(screen, P.HAZARD if hover else P.STEEL_DARK, self.button)
        pygame.draw.rect(screen, P.GUNMETAL, self.button.inflate(-4, -4))
        label = outlined_text(f["normal"], "DEPLOY", P.CRT_GREEN)
        screen.blit(label, label.get_rect(center=self.button.center))

        help_lines = [
            "1-4 build  |  click tower to select  |  U upgrade  S sell  T targeting",
            "SPACE next wave  |  F speed  |  P pause  |  F11 fullscreen",
        ]
        for i, line in enumerate(help_lines):
            img = outlined_text(f["small"], line, P.STEEL_LIGHT)
            screen.blit(img, img.get_rect(center=(WIDTH // 2, 300 + i * 14)))


class UiState:
    def __init__(self):
        self.build_kind = None
        self.selected = None
        self.hover_pad = None
        self.hover_kind = None
        self.mouse = (0, 0)
        self.speed = 1
        self.paused = False


class BattleScene:
    def __init__(self, game, map_name="map01"):
        self.game = game
        self.world = World(map_name)
        self.ui = UiState()
        self.field = FieldRenderer(self.world, game.sprites)
        self.fx = Effects(game.fonts["small"])
        self.hud = Hud((game.fonts["normal"], game.fonts["small"]), game.sprites, self.field)
        self.accumulator = 0.0
        self.over_time = 0.0
        self.fx.say("Commander, the Hive is moving on the colony.")
        self.fx.say("Build turrets on the pads. SPACE when ready.")

    # ---- input ------------------------------------------------------------------

    def handle(self, event):
        w, ui = self.world, self.ui
        if event.type == pygame.MOUSEMOTION:
            ui.mouse = event.pos
        elif event.type == pygame.KEYDOWN:
            self._key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if w.over:
                return
            if event.button == 3:
                ui.build_kind = None
                ui.selected = None
            elif event.button == 1:
                if event.pos[1] >= FIELD_HEIGHT:
                    button = self.hud.button_at(event.pos)
                    if button:
                        self.do(*button.action)
                    return
                pad = w.pad_at(*event.pos)
                if ui.build_kind and pad is not None and pad not in w.towers:
                    tower = w.build(ui.build_kind, pad)
                    if tower and not pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        ui.build_kind = None
                        ui.selected = tower
                elif pad is not None and pad in w.towers:
                    ui.selected = w.towers[pad]
                    ui.build_kind = None
                else:
                    ui.selected = None
                    ui.build_kind = None

    def _key(self, event):
        w, ui, key = self.world, self.ui, event.key
        if w.over:
            if key == pygame.K_r:
                self.game.start_battle()
            elif key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_RETURN):
                self.game.to_menu()
            return
        if ui.paused and key == pygame.K_q:
            self.game.to_menu()
        elif key in BUILD_KEYS:
            self.do("build", BUILD_KEYS[key])
        elif key == pygame.K_u:
            self.do("upgrade")
        elif key == pygame.K_s:
            self.do("sell")
        elif key == pygame.K_t:
            self.do("target")
        elif key == pygame.K_f:
            self.do("speed")
        elif key == pygame.K_SPACE:
            self.do("wave")
        elif key == pygame.K_p:
            ui.paused = not ui.paused
        elif key == pygame.K_ESCAPE:
            if ui.build_kind or ui.selected:
                ui.build_kind = ui.selected = None
            else:
                ui.paused = not ui.paused

    def do(self, action, arg=None):
        w, ui = self.world, self.ui
        if action == "build":
            if w.minerals >= w.build_cost(arg):
                ui.build_kind = None if ui.build_kind == arg else arg
                ui.selected = None
            else:
                self.fx.say("Not enough minerals.")
        elif action == "upgrade" and ui.selected:
            if not w.upgrade(ui.selected):
                self.fx.say("Can't upgrade that." if ui.selected.upgrade_cost is None else "Not enough minerals.")
        elif action == "sell" and ui.selected:
            w.sell(ui.selected)
            ui.selected = None
        elif action == "target" and ui.selected:
            ui.selected.cycle_targeting()
        elif action == "speed":
            ui.speed = SPEEDS[(SPEEDS.index(ui.speed) + 1) % len(SPEEDS)]
        elif action == "wave":
            w.call_wave()

    # ---- update & draw --------------------------------------------------------------

    def update(self, dt):
        w, ui = self.world, self.ui
        mx, my = ui.mouse
        ui.hover_pad = w.pad_at(mx, my) if my < FIELD_HEIGHT else None
        button = self.hud.button_at(ui.mouse)
        ui.hover_kind = button.action[1] if button and button.action[0] == "build" else None
        if ui.selected is not None and ui.selected.pad not in w.towers:
            ui.selected = None

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
            self.over_time += dt
            self.fx.update(dt)
        for name, data in w.drain_events():
            self.fx.handle(name, data, self.field.ground, self.field.rng, self.field.splat)
        self.fx.update_chatter(dt)

    def draw(self, screen):
        screen.fill(P.BLACK)
        field = self.field.draw(self.fx, self.ui)
        ox, oy = self.fx.shake_offset()
        screen.blit(field, (ox, oy))
        self.hud.draw(screen, self.world, self.ui, 1 / FPS)
        self.hud.draw_chatter(screen, self.fx)
        if self.ui.paused and not self.world.over:
            self._overlay(screen, "PAUSED", "P to resume  |  Q quit to menu", P.HAZARD)
        if self.world.over and self.over_time > 0.6:
            if self.world.won:
                self._overlay(screen, "VICTORY", f"Dustfall Ridge holds.  Kills: {self.world.kills}", P.CRT_GREEN,
                              stars=self.world.stars)
            else:
                self._overlay(screen, "CORE DESTROYED", f"The Hive overran the colony on wave "
                                                        f"{self.world.waves.index + 1}.", P.RED)

    def _overlay(self, screen, title, subtitle, color, stars=None):
        f = self.game.fonts
        dim = pygame.Surface((WIDTH, FIELD_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        screen.blit(dim, (0, 0))
        box = pygame.Rect(0, 0, 300, 120 if stars is not None else 96)
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
                self._star(screen, box.centerx - 30 + i * 30, y, i < stars)
            y += 26
        if self.world.over:
            hint = outlined_text(f["small"], "R retry  |  ESC menu", P.CRT_DIM)
            screen.blit(hint, hint.get_rect(center=(box.centerx, y)))

    def _star(self, screen, x, y, filled):
        pts = []
        for i in range(10):
            r = 10 if i % 2 == 0 else 4
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        pygame.draw.polygon(screen, P.HAZARD if filled else P.STEEL_DARK, pts)
        pygame.draw.polygon(screen, P.BLACK, pts, 1)


def main():
    Game().run()
