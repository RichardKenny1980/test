"""The StarCraft-style console along the bottom, plus the resource bar along the top."""
import pygame

from ..settings import FIELD_HEIGHT, HEIGHT, WIDTH
from . import palette as P

TIER_NAMES = ("Mk I", "Mk II", "Mk III")
CARD_X, CARD_Y = 520, FIELD_HEIGHT + 6
BTN_W, BTN_H, GAP = 36, 22, 2


class Button:
    def __init__(self, col, row, action, label, hotkey):
        self.rect = pygame.Rect(CARD_X + col * (BTN_W + GAP), CARD_Y + row * (BTN_H + GAP), BTN_W, BTN_H)
        self.action = action
        self.label = label
        self.hotkey = hotkey


def make_buttons():
    return [
        Button(0, 0, ("build", "bunker"), None, "1"),
        Button(1, 0, ("build", "mortar"), None, "2"),
        Button(2, 0, ("build", "cryo"), None, "3"),
        Button(0, 1, ("build", "missile"), None, "4"),
        Button(1, 1, ("upgrade",), "UPG", "U"),
        Button(2, 1, ("sell",), "SELL", "S"),
        Button(0, 2, ("target",), "AIM", "T"),
        Button(1, 2, ("speed",), "1x", "F"),
        Button(2, 2, ("wave",), "WAVE", "SPC"),
    ]


class Hud:
    def __init__(self, fonts, sprites, field_renderer):
        self.font, self.small = fonts
        self.sprites = sprites
        self.field = field_renderer
        self.buttons = make_buttons()
        self.frame = self._console_frame()
        self.time = 0.0

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
        for rect in ((6, 6, 116, 70), (128, 6, 60, 70), (192, 6, 322, 70), (CARD_X - 4, 3, 122, 76)):
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
        mini = pygame.transform.smoothscale(self.field.ground, area.size)
        screen.blit(mini, area)
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
        kind = ui.build_kind or (ui.hover_kind) or (ui.selected.kind if ui.selected else None)
        if kind:
            tier = ui.selected.tier if ui.selected and ui.selected.kind == kind and not ui.build_kind else 0
            icon = pygame.transform.scale_by(self.sprites.icon(kind, tier), 2)
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
        kind = ui.hover_kind or ui.build_kind
        if kind:
            spec = world.tower_specs[kind]
            st = spec["tiers"][0]
            self._text(screen, spec["name"].upper(), (x, y), P.WHITE, self.font)
            self._cost(screen, st["cost"], (x + 230, y + 3), world.minerals >= st["cost"])
            self._text(screen, spec["role"], (x, y + 18))
            self._stats(screen, spec, st, (x, y + 30))
            traits = ["Targets " + " + ".join(t.upper() for t in spec["targets"])]
            if spec.get("pierce"):
                traits.append("Armor-piercing")
            if spec.get("detector"):
                traits.append("Detector")
            self._text(screen, "  |  ".join(traits), (x, y + 42), P.CRT_DIM)
            if ui.build_kind:
                self._text(screen, "Click a pad to build.  Right-click to cancel.", (x, y + 54), P.CRT_DIM)
            return
        t = ui.selected
        if t is not None and t.pad in world.towers:
            spec = t.spec
            self._text(screen, f"{spec['name'].upper()}  {TIER_NAMES[t.tier]}", (x, y), P.WHITE, self.font)
            self._stats(screen, spec, t.stats, (x, y + 18))
            self._text(screen, f"Targeting: {t.targeting.upper()}  (T)", (x, y + 30))
            if t.upgrade_cost is not None:
                nxt = spec["tiers"][t.tier + 1]
                w = self._text(screen, f"Upgrade to {TIER_NAMES[t.tier + 1]}:", (x, y + 42))
                self._cost(screen, t.upgrade_cost, (x + w + 6, y + 42), world.minerals >= t.upgrade_cost)
                self._text(screen, f"DMG {nxt['damage']}  RNG {nxt['range']}", (x + w + 50, y + 42), P.CRT_DIM)
            else:
                self._text(screen, "Fully upgraded.", (x, y + 42), P.HAZARD)
            self._text(screen, f"Sell for {t.sell_value} (S)", (x, y + 54), P.CRT_DIM)
            return
        waves = world.waves
        self._text(screen, f"WAVE {max(0, waves.index + 1)} / {waves.total}", (x, y), P.WHITE, self.font)
        if waves.has_next:
            ix = x + self._text(screen, "Incoming:", (x, y + 18)) + 6
            for kind, count in waves.preview():
                img = self.sprites.enemy(kind, self.time, 0)
                img = pygame.transform.scale_by(img, 0.6) if img.get_width() > 24 else img
                screen.blit(img, img.get_rect(midleft=(ix, y + 23)))
                ix += img.get_width() + 2
                ix += self._text(screen, f"x{count}", (ix, y + 18), P.WHITE) + 8
            if waves.index < 0:
                self._text(screen, "Build defenses, then press SPACE to launch wave 1.", (x, y + 36), P.CRT_DIM)
            elif waves.countdown is not None:
                self._text(screen, f"Next wave in {int(waves.countdown) + 1}s.  "
                                   f"SPACE to call early: +{int(waves.countdown)} bonus", (x, y + 36), P.HAZARD)
            else:
                self._text(screen, "Enemies still deploying...", (x, y + 36), P.CRT_DIM)
        else:
            self._text(screen, "Final wave! Clear the field.", (x, y + 18), P.HAZARD)
        self._text(screen, f"Kills: {world.kills}", (x, y + 54), P.CRT_DIM)

    def _stats(self, screen, spec, st, pos):
        rate = 1 / st["cooldown"]
        parts = [f"DMG {st['damage']}", f"RATE {rate:.1f}/s", f"RNG {st['range']}"]
        if st.get("splash"):
            parts.append(f"SPLASH {st['splash']}")
        if st.get("slow"):
            parts.append(f"SLOW {int(st['slow'] * 100)}%")
        if st.get("chain"):
            parts.append(f"CHAIN {st['chain']}")
        self._text(screen, "   ".join(parts), pos, P.WHITE)

    def _cost(self, screen, cost, pos, affordable):
        screen.blit(self.sprites.mineral, pos)
        return self._text(screen, str(cost), (pos[0] + 11, pos[1] + 1), P.MINERAL if affordable else P.RED)

    def _command_card(self, screen, world, ui):
        mouse = ui.mouse
        for b in self.buttons:
            enabled, active = True, False
            act = b.action[0]
            if act == "build":
                kind = b.action[1]
                enabled = world.minerals >= world.build_cost(kind)
                active = ui.build_kind == kind
            elif act == "upgrade":
                t = ui.selected
                enabled = t is not None and t.upgrade_cost is not None and world.minerals >= t.upgrade_cost
            elif act in ("sell", "target"):
                enabled = ui.selected is not None
            elif act == "wave":
                enabled = world.waves.can_call
                active = enabled and int(self.time * 2) % 2 == 0 and world.waves.index < 0
            r = b.rect
            hover = r.collidepoint(mouse)
            pygame.draw.rect(screen, P.STEEL_DARK if not active else P.HAZARD, r)
            pygame.draw.rect(screen, P.STEEL if hover and enabled else P.GUNMETAL, r.inflate(-2, -2))
            pygame.draw.line(screen, P.STEEL_LIGHT, r.topleft, r.topright)
            if act == "build":
                icon = self.sprites.icon(b.action[1])
                icon = pygame.transform.scale_by(icon, 0.75)
                if not enabled:
                    icon = icon.copy()
                    icon.set_alpha(90)
                screen.blit(icon, icon.get_rect(center=r.center))
            else:
                label = b.label if act != "speed" else f"{ui.speed}x"
                if act == "target" and ui.selected is not None:
                    label = ui.selected.targeting[:4].upper()
                img = self.small.render(label, False, P.CRT_GREEN if enabled else P.STEEL_DARK)
                screen.blit(img, img.get_rect(midbottom=(r.centerx + 3, r.bottom)))
            key = self.small.render(b.hotkey, False, P.HAZARD if enabled else P.STEEL_DARK)
            screen.blit(key, (r.x + 2, r.y + 1))

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
