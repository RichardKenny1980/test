"""Everything drawn over the battlefield: the resource bar, the floating control buttons and the
details card for the ring menu. There is no console panel, so the battlefield fills the screen."""
import pygame

from ..settings import HEIGHT, WIDTH
from . import palette as P

TIER_NAMES = ("Mk I", "Mk II", "Mk III")
CARD_W, CARD_H = 250, 74
TOP_BAR = (WIDTH - 238, 2, 236, 15)


class Button:
    def __init__(self, rect, action, label, hotkey):
        self.rect = pygame.Rect(rect)
        self.action = action
        self.label = label
        self.hotkey = hotkey


def make_buttons():
    """Big thumb buttons in the bottom-left corner, which the map keeps clear of pads and road."""
    y = HEIGHT - 40
    return [
        Button((4, y, 64, 36), ("wave",), "WAVE", "SPACE"),
        Button((72, y, 44, 36), ("speed",), "1x", "F"),
        Button((120, y, 44, 36), ("pause",), "II", "P"),
    ]


class Hud:
    def __init__(self, fonts, sprites, field_renderer):
        self.font, self.small = fonts
        self.sprites = sprites
        self.field = field_renderer
        self.buttons = make_buttons()
        self.time = 0.0

    def button_at(self, pos):
        for b in self.buttons:
            if b.rect.collidepoint(pos):
                return b
        return None

    # ---- drawing ---------------------------------------------------------------

    def draw(self, screen, world, ui, dt):
        self.time += dt
        self._buttons(screen, world, ui)
        self._top_bar(screen, world, ui)
        if ui.radial is not None:
            self._card(screen, world, ui)

    def _text(self, screen, text, pos, color=P.CRT_GREEN, font=None):
        img = (font or self.small).render(text, False, color)
        screen.blit(img, pos)
        return img.get_width()

    def _panel(self, screen, rect, alpha=200):
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((8, 10, 14, alpha))
        screen.blit(bg, rect)
        pygame.draw.rect(screen, P.STEEL_DARK, rect, 1)

    def _card(self, screen, world, ui):
        """Details for the ring menu, on the side of the screen away from the ring."""
        radial = ui.radial
        x = WIDTH - CARD_W - 4 if radial.cx < WIDTH // 2 else 4
        y = 20 if radial.cx < WIDTH // 2 else 34  # below the resource bar / the radio chatter
        self._panel(screen, pygame.Rect(x, y, CARD_W, CARD_H))
        self._info(screen, world, ui, x + 6, y + 4, x + CARD_W - 6)

    def _info(self, screen, world, ui, x, y, right):
        radial = ui.radial
        armed = radial.armed
        if radial.tower is None:
            if armed is None:
                self._text(screen, "BUILD A TURRET", (x, y), P.WHITE, self.font)
                self._text(screen, "Tap a turret for its details.", (x, y + 18))
                self._text(screen, "Tap it again to build it here.", (x, y + 30))
                self._text(screen, "Tap anywhere else to close.", (x, y + 54), P.CRT_DIM)
                return
            spec = world.tower_specs[armed.arg]
            st = spec["tiers"][0]
            self._text(screen, spec["name"].upper(), (x, y), P.WHITE, self.font)
            self._cost(screen, st["cost"], (right - 40, y + 3), world.minerals >= st["cost"])
            self._text(screen, spec["role"], (x, y + 18))
            self._stats(screen, spec, st, (x, y + 30))
            self._text(screen, self._traits(spec), (x, y + 42), P.CRT_DIM)
            hint = "Tap again to build." if radial.affordable(armed) else "Not enough minerals."
            self._text(screen, hint, (x, y + 54), P.HAZARD if radial.affordable(armed) else P.RED)
            return
        t = radial.tower
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

    def _buttons(self, screen, world, ui):
        waves = world.waves
        for b in self.buttons:
            act = b.action[0]
            enabled, active, label, sub = True, False, b.label, ""
            if act == "speed":
                label = f"{ui.speed}x"
            elif act == "pause":
                label = ">" if ui.paused else "II"
                active = ui.paused
            elif act == "wave":
                enabled = waves.can_call
                active = enabled and int(self.time * 2) % 2 == 0 and waves.index < 0
                if not enabled:
                    sub = ""
                elif waves.index < 0:
                    sub = "START"
                elif waves.countdown is not None:
                    sub = f"{int(waves.countdown) + 1}s"
            r = b.rect
            pressed = ui.pressed is b
            frame = pygame.Surface(r.size, pygame.SRCALPHA)
            frame.fill((*(P.HAZARD if active else P.STEEL_DARK), 230))
            pygame.draw.rect(frame, (*(P.STEEL if pressed else P.GUNMETAL), 215), frame.get_rect().inflate(-4, -4))
            screen.blit(frame, r)
            pygame.draw.line(screen, P.STEEL_LIGHT, (r.x + 2, r.y + 2), (r.right - 3, r.y + 2))
            color = P.CRT_GREEN if enabled else P.STEEL_DARK
            img = self.font.render(label, False, color)
            if sub:
                screen.blit(img, img.get_rect(center=(r.centerx, r.centery - 6)))
                img = self.small.render(sub, False, P.HAZARD)
                screen.blit(img, img.get_rect(center=(r.centerx, r.centery + 9)))
            else:
                screen.blit(img, img.get_rect(center=r.center))

    def _top_bar(self, screen, world, ui):
        bar = pygame.Surface(TOP_BAR[2:], pygame.SRCALPHA)
        bar.fill((10, 10, 16, 170))
        screen.blit(bar, TOP_BAR[:2])
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
