"""Draws the battlefield: terrain, towers, enemies, projectiles and overlays."""
import math
import random

import pygame

from ..settings import FIELD_HEIGHT, WIDTH
from . import palette as P
from .art import SpriteBank, background, goo_splat, radar_dish, scale_by


class FieldRenderer:
    def __init__(self, world, sprites: SpriteBank):
        self.world = world
        self.sprites = sprites
        self.ground = background(world)  # decals (goo, scorch marks) are painted onto this
        self.surface = pygame.Surface((WIDTH, FIELD_HEIGHT))
        self.rng = random.Random(3)
        self.time = 0.0
        self._shadows = {}
        self._ranges = {}
        self.plate = scale_by(sprites.pad, 20 / 26)  # the smaller base plate for grid levels

    def splat(self, rng, radius, flying):
        return goo_splat(rng, radius, flying)

    def draw(self, effects, ui, font):
        w, s, sp = self.world, self.surface, self.sprites
        s.blit(self.ground, (0, 0))

        if w.grid is None:
            for i, (px, py) in enumerate(w.pads):
                s.blit(sp.pad, sp.pad.get_rect(center=(px, py)))
                if ui.radial is not None and i == ui.radial.pad:
                    pygame.draw.rect(s, P.HAZARD, sp.pad.get_rect(center=(px, py)).inflate(2, 2), 1)
        else:
            for pad in w.towers:
                s.blit(self.plate, self.plate.get_rect(center=w.pads[pad]))
            if w.kind == "maze":
                self._route(s, w.path)
            if ui.radial is not None:
                pygame.draw.rect(s, P.HAZARD, pygame.Rect(w.grid.rect(w.pad_cells[ui.radial.pad])).inflate(2, 2), 1)

        core = sp.core[int(self.time * 2) % 2]
        s.blit(core, core.get_rect(center=w.core))

        ground = [e for e in w.enemies if not e.flying]
        air = [e for e in w.enemies if e.flying]

        for e in ground:
            if e.burrowed and not e.detected:
                mound = sp.mound[int(e.age * 8) % 4]
                s.blit(mound, mound.get_rect(center=(int(e.x), int(e.y))))
                continue
            self._shadow(s, e.x, e.y + e.radius * 0.6, e.radius)
            img = sp.enemy(e.kind, e.age, e.heading, flash=e.hit_flash > 0)
            if e.burrowed:
                img = img.copy()
                img.set_alpha(150)
            s.blit(img, img.get_rect(center=(int(e.x), int(e.y))))
            if e.slow > 0:
                self._frost(s, e)

        for tower in sorted(w.towers.values(), key=lambda t: t.y):
            base = sp.tower_bases[tower.kind][tower.tier]
            s.blit(base, base.get_rect(center=(tower.x, tower.y)))
            if tower.kind == "missile":
                dish = sp_dish(self.time * 3)
                s.blit(dish, (tower.x + 3, tower.y + 3))
            kick = tower.recoil * 12
            tx = tower.x - math.cos(tower.angle) * kick
            ty = tower.y - math.sin(tower.angle) * kick
            turret = sp.turret(tower.kind, tower.tier, tower.angle)
            s.blit(turret, turret.get_rect(center=(int(tx), int(ty) - 1)))
            for i in range(tower.tier):
                cx = tower.x - tower.tier * 3 + i * 6
                pygame.draw.polygon(s, P.HAZARD, [(cx, tower.y + 12), (cx + 2, tower.y + 10), (cx + 4, tower.y + 12)])

        for e in air:
            self._shadow(s, e.x + 4, e.y + 14, e.radius)
            img = sp.enemy(e.kind, e.age, e.heading, flash=e.hit_flash > 0)
            s.blit(img, img.get_rect(center=(int(e.x), int(e.y))))
            if e.slow > 0:
                self._frost(s, e)

        for p in w.projectiles:
            self._projectile(s, p)

        effects.draw(s)

        for e in w.enemies:
            if e.targetable and (e.hp < e.max_hp or e.boss):
                self._health_bar(s, e)

        radial = ui.radial
        if radial is not None:
            armed = radial.armed
            px, py = w.pads[radial.pad]
            tower = radial.tower
            if tower is not None:
                r = tower.range
                if armed is not None and armed.action == "upgrade":
                    r = tower.spec["tiers"][tower.tier + 1]["range"]
                self._range(s, px, py, r)
            elif armed is not None:
                self._range(s, px, py, w.tower_specs[armed.arg]["tiers"][0]["range"])
                ghost = sp.icon(armed.arg).copy()
                ghost.set_alpha(150)
                s.blit(ghost, ghost.get_rect(center=(px, py)))
            radial.draw(s, sp, font, self.time)
        return s

    def _route(self, s, path):
        """Maze levels: marching chevrons along the way the Hive will walk right now."""
        offset = (self.time * 24) % 16
        d = offset
        while d < path.length:
            x, y, h = path.position(d)
            if x >= 0:
                tip = (x + math.cos(h) * 3, y + math.sin(h) * 3)
                for side in (-1, 1):
                    a = h + side * 2.4
                    pygame.draw.line(s, P.CREEP_VEIN, tip, (tip[0] + math.cos(a) * 4, tip[1] + math.sin(a) * 4))
            d += 16

    def _shadow(self, s, x, y, r):
        shadow = self._shadows.get(r)
        if shadow is None:
            shadow = self._shadows[r] = pygame.Surface((r * 2 + 2, r + 2), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, P.SHADOW, shadow.get_rect())
        s.blit(shadow, shadow.get_rect(center=(int(x), int(y))))

    def _frost(self, s, e):
        for i in range(3):
            a = e.age * 3 + i * 2.1
            s.set_at((int(e.x + math.cos(a) * e.radius), int(e.y + math.sin(a) * e.radius)), P.CRYO_LIGHT)

    def _health_bar(self, s, e):
        width = max(10, e.radius * 2 + 2)
        x, y = int(e.x - width / 2), int(e.y - e.radius - 6)
        ratio = max(0.0, e.hp / e.max_hp)
        color = P.CRT_GREEN if ratio > 0.5 else P.HAZARD if ratio > 0.25 else P.RED
        pygame.draw.rect(s, P.BLACK, (x - 1, y - 1, width + 2, 4))
        pygame.draw.rect(s, color, (x, y, int(width * ratio), 2))

    def _range(self, s, x, y, r):
        overlay = self._ranges.get(r)
        if overlay is None:
            overlay = self._ranges[r] = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(overlay, (*P.TEAM_BLUE, 40), (r + 1, r + 1), r)
            pygame.draw.circle(overlay, (*P.TEAM_BLUE_LIGHT, 180), (r + 1, r + 1), r, 1)
        s.blit(overlay, (x - r - 1, y - r - 1))

    def _projectile(self, s, p):
        if p.kind == "bullet":
            a = math.atan2(p.ty - p.y, p.tx - p.x)
            pygame.draw.line(s, P.FLASH, (p.x, p.y), (p.x - math.cos(a) * 3, p.y - math.sin(a) * 3))
        elif p.kind == "shell":
            sx, sy = p.start
            total = math.hypot(p.tx - sx, p.ty - sy) or 1
            t = 1 - math.hypot(p.tx - p.x, p.ty - p.y) / total
            lift = math.sin(math.pi * t) * min(40, total * 0.35)
            pygame.draw.circle(s, (40, 30, 20), (int(p.x), int(p.y)), 1)
            pygame.draw.circle(s, P.OUTLINE, (int(p.x), int(p.y - lift)), 3)
            pygame.draw.circle(s, P.STEEL_LIGHT, (int(p.x), int(p.y - lift)), 2)
        elif p.kind == "missile":
            for i, (x, y) in enumerate(p.trail):
                c = 90 + i * 15
                s.set_at((int(x), int(y)), (c, c, c))
            pygame.draw.circle(s, P.FIRE, (int(p.x), int(p.y)), 2)
            s.set_at((int(p.x), int(p.y)), P.FLASH)


_dish_cache = {}


def sp_dish(t):
    key = int(t * 4) % 16
    if key not in _dish_cache:
        _dish_cache[key] = radar_dish(key / 16 * 2 * math.pi)
    return _dish_cache[key]
