"""Touch-friendly ring menu that pops up around a build pad or tower.

Tap an option once to see what it does (info panel + range preview), tap it
again to confirm. This works the same with a mouse, so there is one control
scheme for phone and desktop.
"""
import math

import pygame

from ..settings import FIELD_HEIGHT, WIDTH
from . import palette as P

RING = 36           # distance from the pad centre to each option
OPTION_R = 17       # option button radius (34px, roughly a fingertip once scaled to a phone)
BUILD_ORDER = ("bunker", "mortar", "cryo", "missile")
ANGLES = (-90, 0, 90, 180)  # up, right, down, left
AIM_LABELS = {"first": "FIRST", "last": "LAST", "strongest": "STRONG", "closest": "NEAR"}


class Option:
    def __init__(self, action, arg, x, y):
        self.action, self.arg = action, arg
        self.x, self.y = x, y
        self.confirm = action != "target"  # cycling targeting is harmless, so it applies on the first tap

    def hit(self, pos):
        return math.hypot(pos[0] - self.x, pos[1] - self.y) <= OPTION_R + 3


class RadialMenu:
    def __init__(self, world, pad):
        self.world = world
        self.pad = pad
        px, py = world.pads[pad]
        margin = RING + OPTION_R + 2
        # keep the whole ring on screen; near an edge the ring slides inward
        self.cx = min(max(px, margin), WIDTH - margin)
        self.cy = min(max(py, margin + 10), FIELD_HEIGHT - margin)
        self.armed = None
        self.options = []
        tower = self.tower
        if tower is None:
            for kind, angle in zip(BUILD_ORDER, ANGLES):
                self._add("build", kind, angle)
        else:
            if tower.upgrade_cost is not None:
                self._add("upgrade", None, -90)
            self._add("target", None, 0)
            self._add("sell", None, 90)

    def _add(self, action, arg, angle):
        a = math.radians(angle)
        self.options.append(Option(action, arg, self.cx + math.cos(a) * RING, self.cy + math.sin(a) * RING))

    @property
    def tower(self):
        return self.world.towers.get(self.pad)

    def option_at(self, pos):
        for opt in self.options:
            if opt.hit(pos):
                return opt
        return None

    def cost(self, opt):
        if opt.action == "build":
            return self.world.build_cost(opt.arg)
        if opt.action == "upgrade":
            return self.tower.upgrade_cost
        return 0

    def affordable(self, opt):
        return self.world.minerals >= self.cost(opt)

    # ---- drawing ------------------------------------------------------------------

    def draw(self, surf, sprites, font, time):
        ring = pygame.Surface((WIDTH, FIELD_HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(ring, (0, 0, 0, 70), (self.cx, self.cy), RING + OPTION_R + 2)
        pygame.draw.circle(ring, (*P.HAZARD, 120), (self.cx, self.cy), RING, 1)
        surf.blit(ring, (0, 0))
        for opt in self.options:
            ok = self.affordable(opt)
            armed = opt is self.armed
            pulse = armed and int(time * 4) % 2 == 0
            pygame.draw.circle(surf, P.HAZARD if armed else P.STEEL_DARK, (opt.x, opt.y), OPTION_R)
            pygame.draw.circle(surf, P.STEEL if pulse else P.GUNMETAL, (opt.x, opt.y), OPTION_R - 2)
            if opt.action == "build":
                icon = sprites.icon(opt.arg)
            elif opt.action == "upgrade":
                icon = sprites.icon(self.tower.kind, self.tower.tier + 1)
            else:
                icon = None
            if icon is not None:
                icon = pygame.transform.scale_by(icon, 0.85)
                if not ok:
                    icon = icon.copy()
                    icon.set_alpha(80)
                surf.blit(icon, icon.get_rect(center=(opt.x, opt.y - 2)))
            label, opt_y = None, opt.y
            if opt.action == "sell":
                label, color = f"+{self.tower.sell_value}", P.MINERAL
            elif opt.action == "target":
                label, color = AIM_LABELS[self.tower.targeting], P.CRT_GREEN
                img = font.render("AIM", False, P.CRT_DIM)
                surf.blit(img, img.get_rect(center=(opt.x, opt.y - 7)))
                opt_y = opt.y + 4
            if label:
                img = font.render(label, False, color)
                surf.blit(img, img.get_rect(center=(opt.x, opt_y)))
            cost = self.cost(opt)
            if cost:
                img = font.render(str(cost), False, P.MINERAL if ok else P.RED)
                bg = img.get_rect(midtop=(opt.x, opt.y + OPTION_R - 6)).inflate(4, 0)
                pygame.draw.rect(surf, P.BLACK, bg)
                surf.blit(img, img.get_rect(midtop=(opt.x, opt.y + OPTION_R - 6)))
            if opt.action == "upgrade":
                pygame.draw.polygon(surf, P.HAZARD, [(opt.x - 4, opt.y - OPTION_R + 7),
                                                     (opt.x, opt.y - OPTION_R + 3),
                                                     (opt.x + 4, opt.y - OPTION_R + 7)])
            if armed and opt.confirm:
                img = font.render("TAP AGAIN", False, P.HAZARD)
                bg = img.get_rect(midbottom=(opt.x, opt.y - OPTION_R - 1)).inflate(4, 2)
                pygame.draw.rect(surf, P.BLACK, bg)
                surf.blit(img, img.get_rect(midbottom=(opt.x, opt.y - OPTION_R)))
