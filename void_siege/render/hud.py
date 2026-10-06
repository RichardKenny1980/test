"""The StarCraft-style console along the bottom, plus the resource bar along the top."""
import pygame

from ..settings import FIELD_HEIGHT, HEIGHT, WIDTH
from . import palette as P
from .art import scale_by

TIER_NAMES = ("Mk I", "Mk II", "Mk III")
INFO_RIGHT = 470


class Button:
    def __init__(self, rect, action, label, hotkey):
        self.rect = pygame.Rect(rect)
        self.action = action
        self.label = label
        self.hotkey = hotkey


def make_buttons():
    """Big console buttons, sized for thumbs."""
    y = FIELD_HEIGHT + 5
    return [
        Button((474, y, 78, 34), ("speed",), "1x", "F"),
        Button((474, y + 37, 78, 34), ("pause",), "PAUSE", "P"),
        Button((556, y, 80, 71), ("wave",), "WAVE", "SPACE"),
    ]


class Hud:
    def __init__(self, fonts, sprites, field_renderer):
        self.font, self.small = fonts
        self.sprites = sprites
        self.field = field_renderer
        self.buttons = make_buttons()
        self.frame = self._console_frame()
        self.time = 0.0
        self._mini = None
        self._mini_age = 99.0

    def button_at(self, pos):
        for b in self.buttons:
            if b.rect.collidepoint(pos):
                return b
        return None

    # ---- drawing ---------------------------------------------------------------

    def _console_frame(self):
        s = pygame.Surface((WIDTH, HEIGHT - FIELD_HEIGHT))
        s.fill(P.GUNMETAL)
        pygame.draw.rect(s, P.STEEL_DARK, (0, 0, WIDTH, 3))
        pygame.draw.line(s, P.STEEL_LIGHT, (0, 0), (WIDTH, 0))
        for i in range(0, WIDTH, 10):  # hazard trim
            pygame.draw.line(s, P.HAZARD, (i, 4), (i + 4, 0))
        for x in range(4, WIDTH, 40):
            for y in (8, HEIGHT - FIELD_HEIGHT - 5):
                pygame.draw.circle(s, P.STEEL_DARK, (x, y), 2)
                s.set_at((x - 1, y - 1), P.STEEL_LIGHT)
        for rect in ((6, 6, 116, 70), (128, 6, 60, 70), (192, 6, INFO_RIGHT - 192, 70)):
            r = pygame.Rect(rect)
            pygame.draw.rect(s, P.BLACK, r)
            pygame.draw.rect(s, P.STEEL_DARK, r, 2)
            pygame.draw.line(s, P.STEEL_LIGHT, r.bottomleft, r.bottomright)
        return s

    def draw(self, screen, world, ui, dt):
        self.time += dt
        screen.blit(self.frame, (0, FIELD_HEIGHT))
        self._minimap(screen, world)
        self._portrait(screen, world, ui)
        self._info(screen, world, ui)
        self._command_card(screen, world, ui)
        self._top_bar(screen, world, ui)

    def _text(self, screen, text, pos, color=P.CRT_GREEN, font=None):
        img = (font or self.small).render(text, False, color)
        screen.blit(img, pos)
        return img.get_width()

    def _minimap(self, screen, world):
        area = pygame.Rect(8, FIELD_HEIGHT + 14, 112, 49)
        self._mini_age += 1
        if self._mini is None or self._mini_age > 30:  # the ground only changes when decals land
            self._mini = pygame.transform.smoothscale(self.field.ground, area.size)
            self._mini_age = 0
        screen.blit(self._mini, area)
        sx, sy = area.w / WIDTH, area.h / FIELD_HEIGHT
        for t in world.towers.values():
            screen.fill(P.TEAM_BLUE_LIGHT, (area.x + t.x * sx - 1, area.y + t.y * sy - 1, 2, 2))
        for e in world.enemies:
            if e.targetable:
                screen.fill(P.RED, (area.x + e.x * sx, area.y + e.y * sy, 2 if e.boss else 1, 2 if e.boss else 1))
        pygame.draw.rect(screen, P.CRT_DIM, area, 1)
        self._text(screen, "TACTICAL", (10, FIELD_HEIGHT + 66), P.CRT_DIM)

    def _portrait(self, screen, world, ui):
        area = pygame.Rect(130, FIELD_HEIGHT + 8, 56, 66)
        pygame.draw.rect(screen, P.CRT_BG, area)
        kind, tier = ui.preview_kind, 0
        if kind is None and ui.selected is not None:
            kind, tier = ui.selected.kind, ui.selected.tier
        if kind:
            icon = scale_by(self.sprites.icon(kind, tier), 2)
            screen.blit(icon, icon.get_rect(center=area.center))
        else:
            self._pilot(screen, area)
        tint = pygame.Surface(area.size, pygame.SRCALPHA)
        tint.fill((*P.CRT_GREEN, 40))
        for y in range(0, area.h, 2):
            pygame.draw.line(tint, (0, 0, 0, 90), (0, y), (area.w, y))
        screen.blit(tint, area)
        pygame.draw.rect(screen, P.CRT_DIM, area, 1)

    def _pilot(self, screen, area):
        cx, cy = area.centerx, area.centery + 6
        talk = int(self.time * 6) % 3
        pygame.draw.rect(screen, P.STEEL_DARK, (cx - 18, cy + 12, 36, 14))  # shoulders
        pygame.draw.ellipse(screen, P.STEEL, (cx - 14, cy - 20, 28, 34))   # helmet
        pygame.draw.ellipse(screen, P.STEEL_LIGHT, (cx - 10, cy - 18, 12, 8))
        pygame.draw.rect(screen, P.TEAM_BLUE, (cx - 10, cy - 6, 20, 7))    # visor
        pygame.draw.line(screen, P.TEAM_BLUE_LIGHT, (cx - 8, cy - 5), (cx + 2, cy - 5))
        pygame.draw.rect(screen, P.GUNMETAL, (cx - 5, cy + 5, 10, 2 + talk))  # mouth grille

    def _info(self, screen, world, ui):
        x, y = 198, FIELD_HEIGHT + 8
        radial = ui.radial
        armed = radial.armed if radial else None
        if radial is not None and radial.tower is None:
            if armed is None:
                self._text(screen, "BUILD A TURRET", (x, y), P.WHITE, self.font)
                self._text(screen, "Tap a turret for its details.", (x, y + 18))
                self._text(screen, "Tap it again to build it here.", (x, y + 30))
                self._text(screen, "Tap anywhere else to close.", (x, y + 54), P.CRT_DIM)
                return
            spec = world.tower_specs[armed.arg]
            st = spec["tiers"][0]
            self._text(screen, spec["name"].upper(), (x, y), P.WHITE, self.font)
            self._cost(screen, st["cost"], (INFO_RIGHT - 40, y + 3), world.minerals >= st["cost"])
            self._text(screen, spec["role"], (x, y + 18))
            self._stats(screen, spec, st, (x, y + 30))
            self._text(screen, self._traits(spec), (x, y + 42), P.CRT_DIM)
            hint = "Tap again to build." if radial.affordable(armed) else "Not enough minerals."
            self._text(screen, hint, (x, y + 54), P.HAZARD if radial.affordable(armed) else P.RED)
            return
        t = ui.selected
        if t is not None:
            spec = t.spec
            self._text(screen, f"{spec['name'].upper()}  {TIER_NAMES[t.tier]}", (x, y), P.WHITE, self.font)
            self._stats(screen, spec, t.stats, (x, y + 18))
            self._text(screen, f"Targeting: {t.targeting.upper()}", (x, y + 30))
            if armed is not None and armed.action == "upgrade":
                nxt = spec["tiers"][t.tier + 1]
                w = self._text(screen, f"{TIER_NAMES[t.tier + 1]}:", (x, y + 42), P.HAZARD)
                self._stats(screen, spec, nxt, (x + w + 4, y + 42))
                ok = world.minerals >= t.upgrade_cost
                self._text(screen, "Tap again to upgrade." if ok else "Not enough minerals.", (x, y + 54),
                           P.HAZARD if ok else P.RED)
            elif armed is not None and armed.action == "sell":
                self._text(screen, f"Tap again to sell for {t.sell_value}.", (x, y + 54), P.HAZARD)
            elif t.upgrade_cost is None:
                self._text(screen, "Fully upgraded.", (x, y + 42), P.HAZARD)
            else:
                self._text(screen, self._traits(spec), (x, y + 42), P.CRT_DIM)
            return
        waves = world.waves
        self._text(screen, f"WAVE {max(0, waves.index + 1)} / {waves.total}", (x, y), P.WHITE, self.font)
        if waves.has_next:
            ix = x + self._text(screen, "Incoming:", (x, y + 18)) + 6
            for kind, count in waves.preview():
                img = self.sprites.enemy(kind, self.time, 0)
                img = scale_by(img, 0.6) if img.get_width() > 24 else img
                screen.blit(img, img.get_rect(midleft=(ix, y + 23)))
                ix += img.get_width() + 2
                ix += self._text(screen, f"x{count}", (ix, y + 18), P.WHITE) + 8
            if waves.index < 0:
                self._text(screen, "Tap a pad to build turrets.", (x, y + 32), P.CRT_DIM)
                self._text(screen, "Tap WAVE when you're ready.", (x, y + 43), P.CRT_DIM)
            elif waves.countdown is not None:
                self._text(screen, f"Next wave in {int(waves.countdown) + 1}s.", (x, y + 32), P.HAZARD)
                self._text(screen, f"Call it early for +{int(waves.countdown)} bonus.", (x, y + 43), P.HAZARD)
            else:
                self._text(screen, "Enemies still deploying...", (x, y + 32), P.CRT_DIM)
        else:
            self._text(screen, "Final wave! Clear the field.", (x, y + 18), P.HAZARD)
        self._text(screen, f"Kills: {world.kills}", (x, y + 54), P.CRT_DIM)

    def _traits(self, spec):
        traits = ["Hits " + " + ".join(t.upper() for t in spec["targets"])]
        if spec.get("pierce"):
            traits.append("Armor-piercing")
        if spec.get("detector"):
            traits.append("Detector")
        return "  |  ".join(traits)

    def _stats(self, screen, spec, st, pos):
        rate = 1 / st["cooldown"]
        parts = [f"DMG {st['damage']}", f"RATE {rate:.1f}", f"RNG {st['range']}"]
        if st.get("splash"):
            parts.append(f"SPLASH {st['splash']}")
        if st.get("slow"):
            parts.append(f"SLOW {int(st['slow'] * 100)}%")
        if st.get("chain"):
            parts.append(f"CHAIN {st['chain']}")
        self._text(screen, "  ".join(parts), pos, P.WHITE)

    def _cost(self, screen, cost, pos, affordable):
        screen.blit(self.sprites.mineral, pos)
        return self._text(screen, str(cost), (pos[0] + 11, pos[1] + 1), P.MINERAL if affordable else P.RED)

    def _command_card(self, screen, world, ui):
        for b in self.buttons:
            act = b.action[0]
            enabled, active, label = True, False, b.label
            if act == "speed":
                label = f"{ui.speed}x SPEED"
            elif act == "pause":
                label = "RESUME" if ui.paused else "PAUSE"
                active = ui.paused
            elif act == "wave":
                enabled = world.waves.can_call
                active = enabled and int(self.time * 2) % 2 == 0 and world.waves.index < 0
            r = b.rect
            pressed = ui.pressed is b
            pygame.draw.rect(screen, P.HAZARD if active else P.STEEL_DARK, r)
            pygame.draw.rect(screen, P.STEEL if pressed else P.GUNMETAL, r.inflate(-4, -4))
            pygame.draw.line(screen, P.STEEL_LIGHT, (r.x + 2, r.y + 2), (r.right - 3, r.y + 2))
            color = P.CRT_GREEN if enabled else P.STEEL_DARK
            if act == "wave":
                img = self.font.render(label, False, color)
                screen.blit(img, img.get_rect(center=(r.centerx, r.centery - 8)))
                sub = "CALL EARLY" if world.waves.countdown is not None else (
                    "START" if world.waves.index < 0 else "")
                if sub and enabled:
                    img = self.small.render(sub, False, P.HAZARD)
                    screen.blit(img, img.get_rect(center=(r.centerx, r.centery + 8)))
                for i in range(3):  # chevrons
                    cx = r.centerx - 8 + i * 8
                    pygame.draw.polygon(screen, color, [(cx, r.bottom - 14), (cx + 4, r.bottom - 10),
                                                        (cx, r.bottom - 6)])
            else:
                img = self.small.render(label, False, color)
                screen.blit(img, img.get_rect(center=r.center))

    def _top_bar(self, screen, world, ui):
        bar = pygame.Surface((236, 15), pygame.SRCALPHA)
        bar.fill((10, 10, 16, 170))
        screen.blit(bar, (WIDTH - 238, 2))
        x = WIDTH - 232
        screen.blit(self.sprites.mineral, (x, 4))
        self._text(screen, str(world.minerals), (x + 11, 5), P.MINERAL)
        x += 58
        screen.blit(self.sprites.heart, (x, 4))
        hp_color = P.CRT_GREEN if world.core_hp > world.max_core_hp / 2 else P.HAZARD if world.core_hp > 5 else P.RED
        self._text(screen, f"{world.core_hp}/{world.max_core_hp}", (x + 13, 5), hp_color)
        x += 58
        self._text(screen, f"WAVE {max(0, world.waves.index + 1)}/{world.waves.total}", (x, 5), P.WHITE)
        x += 70
        self._text(screen, "PAUSE" if ui.paused else f"{ui.speed}x", (x, 5), P.HAZARD if ui.paused else P.CRT_GREEN)

    def draw_chatter(self, screen, effects):
        for i, (text, life) in enumerate(effects.chatter):
            img = self.small.render(text, False, P.CRT_GREEN)
            img.set_alpha(int(255 * min(1.0, life)))
            bg = pygame.Surface((img.get_width() + 6, img.get_height() + 2), pygame.SRCALPHA)
            bg.fill((0, 10, 0, int(150 * min(1.0, life))))
            screen.blit(bg, (4, 4 + i * 13))
            screen.blit(img, (7, 5 + i * 13))
