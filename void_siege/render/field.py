"""Draws the battlefield: terrain, towers, enemies, projectiles and overlays."""
import math
import random

import pygame

from ..settings import FIELD_HEIGHT, WIDTH
from . import palette as P
from .art import SpriteBank, background, goo_splat, radar_dish


class FieldRenderer:
    def __init__(self, world, sprites: SpriteBank):
        self.world = world
        self.sprites = sprites
        self.ground = background(world)  # decals (goo, scorch marks) are painted onto this
        self.surface = pygame.Surface((WIDTH, FIELD_HEIGHT))
        self.rng = random.Random(3)
        self.time = 0.0

    def splat(self, rng, radius, flying):
        return goo_splat(rng, radius, flying)

    def draw(self, effects, ui):
        w, s, sp = self.world, self.surface, self.sprites
        s.blit(self.ground, (0, 0))

        for i, (px, py) in enumerate(w.pads):
            s.blit(sp.pad, sp.pad.get_rect(center=(px, py)))
            if ui.build_kind and i not in w.towers and i == ui.hover_pad:
                pygame.draw.rect(s, P.HAZARD, sp.pad.get_rect(center=(px, py)).inflate(2, 2), 1)

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

        if ui.selected is not None and ui.selected.pad in w.towers:
            t = ui.selected
            self._range(s, t.x, t.y, t.range)
            pygame.draw.rect(s, P.CRT_GREEN, sp.pad.get_rect(center=(t.x, t.y)).inflate(2, 2), 1)
        if ui.build_kind and ui.hover_pad is not None and ui.hover_pad not in w.towers:
            px, py = w.pads[ui.hover_pad]
            spec = w.tower_specs[ui.build_kind]
            self._range(s, px, py, spec["tiers"][0]["range"])
            ghost = sp.icon(ui.build_kind).copy()
            ghost.set_alpha(150)
            s.blit(ghost, ghost.get_rect(center=(px, py)))
        return s

    def _shadow(self, s, x, y, r):
        shadow = pygame.Surface((r * 2 + 2, r + 2), pygame.SRCALPHA)
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
        overlay = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
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
