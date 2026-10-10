"""Procedural sprites in a StarCraft-1-ish cartoon style.

Everything is drawn with pygame primitives at low resolution, then given a dark
1px outline, which is what sells the chunky late-90s look once scaled up.
"""
import math
import random

import pygame

from . import palette as P

FACINGS = 16


def outline(surface, color=P.OUTLINE):
    """Return a copy of `surface` 2px larger with a 1px outline around its opaque pixels."""
    w, h = surface.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    silhouette = pygame.mask.from_surface(surface).to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(silhouette, (dx, dy))
    out.blit(surface, (1, 1))
    return out


def canvas(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def shade(color, amount):
    return tuple(max(0, min(255, int(c * amount))) for c in color[:3])


def scale_by(surface, factor):
    """pygame.transform.scale_by, which older pygame (the Android build's 2.1) lacks."""
    w, h = surface.get_size()
    return pygame.transform.scale(surface, (max(1, round(w * factor)), max(1, round(h * factor))))


def rotations(surface):
    """Pre-rotate a right-facing sprite into FACINGS headings."""
    return [pygame.transform.rotate(surface, -i * 360 / FACINGS) for i in range(FACINGS)]


def facing_index(angle):
    return round(angle / (2 * math.pi) * FACINGS) % FACINGS


# ---------------------------------------------------------------- enemies

def _skitterling(frame):
    s = canvas(14, 12)
    legs = (-2, 2) if frame % 2 else (2, -2)
    for i, lx in enumerate((4, 7, 10)):
        off = legs[i % 2]
        pygame.draw.line(s, P.HIVE_PURPLE_DARK, (lx, 6), (lx + off, 0), 1)
        pygame.draw.line(s, P.HIVE_PURPLE_DARK, (lx, 6), (lx - off, 11), 1)
    pygame.draw.ellipse(s, P.HIVE_PURPLE, (2, 3, 9, 6))
    pygame.draw.line(s, shade(P.HIVE_PURPLE, 1.4), (4, 4), (8, 4))
    pygame.draw.circle(s, P.HIVE_MAROON, (11, 6), 2)
    s.set_at((12, 5), P.TOXIC)
    s.set_at((12, 7), P.TOXIC)
    return outline(s)


def _spine_brute(frame):
    s = canvas(26, 24)
    step = 2 if frame % 2 else -2
    for y, off in ((3, step), (20, -step)):
        pygame.draw.rect(s, P.HIVE_MAROON_DARK, (8 + off, y, 4, 3))
        pygame.draw.rect(s, P.HIVE_MAROON_DARK, (15 - off, y, 4, 3))
    pygame.draw.ellipse(s, P.HIVE_MAROON, (3, 5, 18, 15))
    pygame.draw.ellipse(s, shade(P.HIVE_MAROON, 1.3), (6, 7, 10, 5))
    for x in (5, 9, 13):
        pygame.draw.polygon(s, P.BONE, [(x, 12), (x + 3, 9), (x + 2, 13)])
        pygame.draw.polygon(s, P.BONE, [(x, 13), (x + 3, 16), (x + 2, 12)])
    pygame.draw.polygon(s, P.BONE, [(20, 6), (25, 9), (21, 10)])
    pygame.draw.polygon(s, P.BONE, [(20, 18), (25, 15), (21, 14)])
    pygame.draw.circle(s, P.HIVE_MAROON_DARK, (20, 12), 4)
    s.set_at((22, 11), P.TOXIC)
    s.set_at((22, 13), P.TOXIC)
    return outline(s)


def _carapace_crawler(frame):
    s = canvas(20, 18)
    off = 1 if frame % 2 else -1
    for lx in (5, 9, 13):
        pygame.draw.line(s, P.ROCK_DARK, (lx, 9), (lx + off, 1))
        pygame.draw.line(s, P.ROCK_DARK, (lx, 9), (lx - off, 16))
        off = -off
    pygame.draw.ellipse(s, P.BONE_DARK, (2, 3, 14, 12))
    pygame.draw.ellipse(s, P.BONE, (3, 4, 11, 6))
    pygame.draw.line(s, P.ROCK_DARK, (3, 9), (15, 9))
    for x in (6, 10):
        pygame.draw.line(s, P.ROCK_DARK, (x, 4), (x, 14))
    pygame.draw.circle(s, P.HIVE_PURPLE_DARK, (16, 9), 3)
    s.set_at((18, 8), P.TOXIC)
    s.set_at((18, 10), P.TOXIC)
    return outline(s)


def _gloomwing(frame):
    s = canvas(20, 24)
    span = (11, 7, 3, 7)[frame % 4]
    membrane = (*P.HIVE_PURPLE, 220)
    pygame.draw.polygon(s, membrane, [(6, 12), (12, 12), (4, 12 - span), (1, 12 - span + 3)])
    pygame.draw.polygon(s, membrane, [(6, 12), (12, 12), (4, 12 + span), (1, 12 + span - 3)])
    pygame.draw.line(s, P.HIVE_PURPLE_DARK, (9, 12), (3, 12 - span))
    pygame.draw.line(s, P.HIVE_PURPLE_DARK, (9, 12), (3, 12 + span))
    pygame.draw.ellipse(s, P.HIVE_MAROON, (5, 10, 12, 5))
    pygame.draw.circle(s, P.HIVE_MAROON_DARK, (16, 12), 2)
    s.set_at((17, 12), P.TOXIC)
    pygame.draw.line(s, P.HIVE_MAROON_DARK, (5, 12), (1, 12))
    return outline(s)


def _burrower(frame):
    s = canvas(18, 12)
    wiggle = (0, 1, 0, -1)[frame % 4]
    for i in range(4):
        x = 2 + i * 3
        y = 6 + (wiggle if i % 2 else -wiggle)
        pygame.draw.circle(s, P.FLESH if i % 2 else P.FLESH_DARK, (x, y), 3)
    pygame.draw.circle(s, P.FLESH, (14, 6), 4)
    pygame.draw.line(s, P.HIVE_MAROON_DARK, (16, 4), (17, 6))
    pygame.draw.line(s, P.HIVE_MAROON_DARK, (16, 8), (17, 6))
    return outline(s)


def _hive_titan(frame):
    s = canvas(48, 44)
    step = 3 if frame % 2 else -3
    for x, y in ((12, 3), (26, 3), (12, 37), (26, 37)):
        off = step if x == 12 else -step
        pygame.draw.rect(s, P.HIVE_PURPLE_DARK, (x + off, y, 7, 5))
    pygame.draw.ellipse(s, P.HIVE_PURPLE, (4, 6, 36, 32))
    pygame.draw.ellipse(s, shade(P.HIVE_PURPLE, 1.25), (9, 9, 22, 12))
    for (x, y) in ((12, 26), (20, 30), (26, 24)):
        pygame.draw.circle(s, P.GOO_DARK, (x, y), 4)
        pygame.draw.circle(s, P.TOXIC, (x - 1, y - 1), 2)
    for x in (8, 15, 22, 29):
        pygame.draw.polygon(s, P.BONE, [(x, 9), (x + 5, 1), (x + 4, 10)])
        pygame.draw.polygon(s, P.BONE, [(x, 35), (x + 5, 43), (x + 4, 34)])
    pygame.draw.circle(s, P.HIVE_MAROON, (38, 22), 8)
    pygame.draw.polygon(s, P.BONE, [(42, 15), (47, 19), (43, 21)])
    pygame.draw.polygon(s, P.BONE, [(42, 29), (47, 25), (43, 23)])
    for y in (19, 25):
        pygame.draw.rect(s, P.TOXIC, (41, y, 2, 2))
    return outline(s)


ENEMY_DRAWERS = {
    "skitterling": (_skitterling, 2),
    "spine_brute": (_spine_brute, 2),
    "carapace_crawler": (_carapace_crawler, 2),
    "gloomwing": (_gloomwing, 4),
    "burrower": (_burrower, 4),
    "hive_titan": (_hive_titan, 2),
}


def burrow_mound(frame):
    s = canvas(14, 8)
    pygame.draw.ellipse(s, P.ROCK, (1, 2, 12, 6))
    pygame.draw.ellipse(s, P.SAND_DARK, (3, 2, 7, 3))
    for i in range(3):
        s.set_at(((frame * 3 + i * 5) % 14, 1 + i % 2), P.ROCK_DARK)
    return outline(s)


# ---------------------------------------------------------------- towers

def pad():
    s = canvas(26, 26)
    pygame.draw.rect(s, P.STEEL_DARK, (0, 0, 26, 26))
    pygame.draw.rect(s, P.STEEL, (1, 1, 24, 24))
    pygame.draw.rect(s, P.GUNMETAL, (4, 4, 18, 18))
    for cx, cy in ((0, 0), (20, 0), (0, 20), (20, 20)):
        for i in range(0, 6, 2):
            pygame.draw.line(s, P.HAZARD, (cx + i, cy), (cx, cy + i))
            pygame.draw.line(s, P.HAZARD, (cx + 5, cy + i + 1), (cx + i + 1, cy + 5))
    for x, y in ((2, 12), (23, 12), (12, 2), (12, 23)):
        s.set_at((x, y), P.STEEL_LIGHT)
    return s


def _base_bunker(tier):
    s = canvas(24, 24)
    for i in range(10):
        a = i / 10 * 2 * math.pi
        pygame.draw.circle(s, P.SAND_DARK, (12 + int(math.cos(a) * 9), 12 + int(math.sin(a) * 9)), 3)
        pygame.draw.circle(s, P.SAND_LIGHT, (11 + int(math.cos(a) * 9), 11 + int(math.sin(a) * 9)), 1)
    pygame.draw.rect(s, P.STEEL_DARK, (6, 6, 12, 12), border_radius=2)
    pygame.draw.rect(s, P.STEEL, (7, 7, 10, 9), border_radius=2)
    return outline(s)


def _turret_bunker(tier):
    s = canvas(22, 14)
    barrels = (1, 2, 3)[tier]
    length = (8, 9, 10)[tier]
    for i in range(barrels):
        y = 7 - (barrels - 1) * 2 + i * 4 - 1
        pygame.draw.rect(s, P.GUNMETAL, (11, y, length, 3))
        pygame.draw.line(s, P.STEEL_LIGHT, (12, y), (10 + length, y))
    pygame.draw.rect(s, P.STEEL_DARK, (4, 2, 10, 10), border_radius=2)
    pygame.draw.rect(s, P.STEEL, (5, 3, 8, 6), border_radius=2)
    pygame.draw.rect(s, P.TEAM_BLUE, (6, 9, 6, 2))
    if tier:
        pygame.draw.line(s, P.HAZARD, (5, 3), (5, 3 + tier * 3))
    return outline(s)


def _base_mortar(tier):
    s = canvas(26, 26)
    for x, y in ((2, 2), (19, 2), (2, 19), (19, 19)):
        pygame.draw.line(s, P.GUNMETAL, (13, 13), (x + 2, y + 2), 3)
        pygame.draw.rect(s, P.STEEL_DARK, (x, y, 5, 5))
    pygame.draw.rect(s, P.RUST, (6, 7, 14, 12), border_radius=2)
    pygame.draw.rect(s, shade(P.RUST, 1.25), (7, 8, 12, 4))
    for i in range(3):
        pygame.draw.line(s, P.HAZARD if i % 2 else P.BLACK, (7 + i * 4, 17), (9 + i * 4, 15))
    return outline(s)


def _turret_mortar(tier):
    s = canvas(26, 16)
    width = (5, 6, 7)[tier]
    length = (11, 13, 14)[tier]
    pygame.draw.rect(s, P.GUNMETAL, (11, 8 - width // 2, length, width))
    pygame.draw.rect(s, P.STEEL_DARK, (10 + length, 8 - width // 2 - 1, 2, width + 2))
    pygame.draw.line(s, P.STEEL_LIGHT, (12, 8 - width // 2), (9 + length, 8 - width // 2))
    pygame.draw.circle(s, P.STEEL_DARK, (9, 8), 7)
    pygame.draw.circle(s, P.STEEL, (8, 7), 5)
    pygame.draw.rect(s, P.TEAM_BLUE, (5, 6, 3, 3))
    if tier == 2:
        pygame.draw.rect(s, P.HAZARD, (14, 8 - width // 2, 2, width))
    return outline(s)


def _base_cryo(tier):
    s = canvas(24, 24)
    pygame.draw.circle(s, P.STEEL_DARK, (12, 12), 10)
    pygame.draw.circle(s, P.STEEL, (12, 12), 8)
    for i in range(6):
        a = i / 6 * 2 * math.pi
        s.set_at((12 + int(math.cos(a) * 9), 12 + int(math.sin(a) * 9)), P.CRYO)
    return outline(s)


def _turret_cryo(tier):
    s = canvas(22, 16)
    pygame.draw.rect(s, P.GUNMETAL, (8, 6, 10, 4))
    for i in range(tier + 2):
        pygame.draw.rect(s, P.CRYO if i % 2 == 0 else P.TEAM_BLUE, (9 + i * 3, 4, 2, 8))
    pygame.draw.circle(s, P.CRYO_LIGHT, (19, 8), 2)
    pygame.draw.circle(s, P.STEEL_DARK, (6, 8), 5)
    pygame.draw.circle(s, P.CRYO, (6, 8), 3)
    pygame.draw.circle(s, P.CRYO_LIGHT, (5, 7), 1)
    return outline(s)


def _base_missile(tier):
    s = canvas(24, 24)
    pts = [(12 + int(math.cos(a) * 10), 12 + int(math.sin(a) * 10))
           for a in (i / 6 * 2 * math.pi + math.pi / 6 for i in range(6))]
    pygame.draw.polygon(s, P.STEEL_DARK, pts)
    pts = [(12 + int(math.cos(a) * 8), 12 + int(math.sin(a) * 8))
           for a in (i / 6 * 2 * math.pi + math.pi / 6 for i in range(6))]
    pygame.draw.polygon(s, P.STEEL, pts)
    pygame.draw.circle(s, P.GUNMETAL, (12, 12), 4)
    return outline(s)


def _turret_missile(tier):
    s = canvas(20, 18)
    rows = (2, 2, 3)[tier]
    pygame.draw.rect(s, P.STEEL_DARK, (4, 9 - rows * 3, 12, rows * 6), border_radius=1)
    pygame.draw.rect(s, P.STEEL, (5, 10 - rows * 3, 10, 2))
    for r in range(rows):
        for c in range(2):
            y = 9 - rows * 3 + 1 + r * 6
            pygame.draw.rect(s, P.GUNMETAL, (11 + c * 3, y, 3, 4))
            pygame.draw.rect(s, P.RED, (16, y + 1, 2, 2))
    if tier:
        pygame.draw.line(s, P.HAZARD, (4, 9 - rows * 3), (4, 8 + rows * 3))
    return outline(s)


def radar_dish(angle):
    s = canvas(10, 10)
    pygame.draw.arc(s, P.STEEL_LIGHT, (1, 1, 8, 8), angle - 0.9, angle + 0.9, 2)
    pygame.draw.line(s, P.STEEL_LIGHT, (5, 5), (5 + int(math.cos(angle) * 3), 5 - int(math.sin(angle) * 3)))
    return s


TOWER_DRAWERS = {
    "bunker": (_base_bunker, _turret_bunker),
    "mortar": (_base_mortar, _turret_mortar),
    "cryo": (_base_cryo, _turret_cryo),
    "missile": (_base_missile, _turret_missile),
}


# ---------------------------------------------------------------- buildings & terrain

def command_core(blink):
    s = canvas(40, 40)
    pts = [(20, 2), (36, 10), (36, 30), (20, 38), (4, 30), (4, 10)]
    pygame.draw.polygon(s, P.STEEL_DARK, pts)
    pygame.draw.polygon(s, P.STEEL, [(20, 5), (33, 12), (33, 22), (20, 28), (7, 22), (7, 12)])
    pygame.draw.polygon(s, P.STEEL_LIGHT, [(20, 5), (33, 12), (20, 18), (7, 12)])
    pygame.draw.rect(s, P.GUNMETAL, (15, 26, 10, 10))
    for i in range(3):
        pygame.draw.line(s, P.HAZARD if i % 2 else P.BLACK, (15 + i * 3, 36), (18 + i * 3, 33))
    pygame.draw.circle(s, P.TEAM_BLUE_LIGHT if blink else P.TEAM_BLUE, (20, 15), 3)
    for x in (9, 31):
        s.set_at((x, 25), P.RED if blink else P.HIVE_MAROON)
    return outline(s)


def background(world, seed=7):
    """Paint the static map: badlands, alien creep at the spawn, the road (none on maze levels),
    rock ridges, faint build-grid marks on open ground, and the core platform."""
    from ..settings import FIELD_HEIGHT, WIDTH

    rng = random.Random(seed)
    s = pygame.Surface((WIDTH, FIELD_HEIGHT))
    s.fill(P.SAND)
    for _ in range(2600):
        x, y = rng.randrange(WIDTH), rng.randrange(FIELD_HEIGHT)
        s.set_at((x, y), rng.choice((P.SAND_DARK, P.SAND_LIGHT, P.SAND_DARK)))
    for _ in range(14):  # darker dust patches
        x, y = rng.randrange(WIDTH), rng.randrange(FIELD_HEIGHT)
        w, h = rng.randrange(40, 110), rng.randrange(16, 40)
        patch = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(patch, (*P.SAND_DARK, 90), patch.get_rect())
        s.blit(patch, (x - w // 2, y - h // 2))
    road = world.kind != "maze"
    for _ in range(9 if world.grid is None else 0):  # craters (they would look like obstacles on a grid)
        x, y, r = rng.randrange(WIDTH), rng.randrange(FIELD_HEIGHT), rng.randrange(5, 12)
        if world.path.distance_to(x, y) < r + 16:
            continue
        pygame.draw.ellipse(s, P.SAND_LIGHT, (x - r, y - r // 2 - 1, r * 2, r))
        pygame.draw.ellipse(s, P.ROCK, (x - r + 2, y - r // 2 + 1, r * 2 - 4, r - 2))
        pygame.draw.ellipse(s, P.ROCK_DARK, (x - r + 4, y - r // 2 + 2, r * 2 - 8, r - 4))
    for _ in range(40):  # rocks
        x, y = rng.randrange(WIDTH), rng.randrange(FIELD_HEIGHT)
        if road and world.path.distance_to(x, y) < 18:
            continue
        if world.grid is None and any(math.hypot(x - px, y - py) < 18 for px, py in world.pads):
            continue
        r = rng.randrange(2, 5)
        pygame.draw.circle(s, P.ROCK_DARK, (x + 1, y + 1), r)
        pygame.draw.circle(s, P.ROCK, (x, y), r)
        s.set_at((x - 1, y - 1), P.SAND_LIGHT)

    # alien creep spreading from the spawn tunnel
    sx, sy = world.spawn_point
    creep = pygame.Surface((WIDTH, FIELD_HEIGHT), pygame.SRCALPHA)
    for _ in range(70):
        a, d = rng.uniform(-1.6, 1.6), rng.uniform(0, 70)
        x, y = sx + 16 + math.cos(a) * d, sy + math.sin(a) * d * 0.8
        r = rng.randrange(6, 16)
        pygame.draw.circle(creep, (*P.CREEP, 255), (int(x), int(y)), r)
    for _ in range(30):
        a, d = rng.uniform(-1.6, 1.6), rng.uniform(0, 60)
        x, y = sx + 16 + math.cos(a) * d, sy + math.sin(a) * d * 0.8
        pygame.draw.circle(creep, (*P.CREEP_DARK, 255), (int(x), int(y)), rng.randrange(2, 6))
    s.blit(creep, (0, 0))
    for _ in range(18):  # veins
        a = rng.uniform(-1.4, 1.4)
        x, y = sx + 10, sy
        for _ in range(8):
            nx, ny = x + math.cos(a) * 7, y + math.sin(a) * 6
            pygame.draw.line(s, P.CREEP_VEIN, (x, y), (nx, ny))
            x, y, a = nx, ny, a + rng.uniform(-0.5, 0.5)

    if road:
        pts = [(int(x), int(y)) for x, y in world.path.points]
        for width, color in ((28, P.ROAD_EDGE), (22, P.ROAD)):
            pygame.draw.lines(s, color, False, pts, width)
            for p in pts:
                pygame.draw.circle(s, color, p, width // 2)
        for d in range(0, int(world.path.length), 5):  # tread marks
            x, y, h = world.path.position(d)
            for side in (-5, 5):
                ox, oy = -math.sin(h) * side, math.cos(h) * side
                s.set_at((int(x + ox), int(y + oy)), P.ROAD_EDGE)
    if world.grid is not None:
        _grid_marks(s, world, rng)
    # spawn tunnel
    pygame.draw.ellipse(s, P.CREEP_DARK, (sx - 10, sy - 14, 30, 28))
    pygame.draw.ellipse(s, P.BLACK, (sx - 4, sy - 9, 20, 18))

    # core platform
    cx, cy = world.core
    pygame.draw.rect(s, P.STEEL_DARK, (cx - 30, cy - 30, 60, 60))
    pygame.draw.rect(s, P.GUNMETAL, (cx - 28, cy - 28, 56, 56))
    for i in range(-28, 28, 8):
        pygame.draw.line(s, P.STEEL_DARK, (cx - 28, cy + i), (cx + 27, cy + i))
    for i in range(0, 56, 6):
        pygame.draw.line(s, P.HAZARD, (cx - 28 + i, cy + 27), (cx - 25 + i, cy + 24))
    return s


def _grid_marks(s, world, rng):
    """Corner ticks on every buildable cell, so open ground reads as "you can build here", and
    boulders on the rock cells that nothing can cross."""
    g = world.grid
    for cell in world.pad_cells:
        x, y, w, h = (int(v) for v in g.rect(cell))
        for cx, cy, dx, dy in ((x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1), (x + w - 1, y + h - 1, -1, -1)):
            s.set_at((cx, cy), P.SAND_DARK)
            s.set_at((cx + dx, cy), P.SAND_DARK)
            s.set_at((cx, cy + dy), P.SAND_DARK)
    for cell in sorted(g.rocks, key=lambda c: c[1]):
        x, y = g.center(cell)
        for _ in range(3):
            ox, oy, r = rng.randrange(-4, 5), rng.randrange(-4, 5), rng.randrange(6, 10)
            pygame.draw.circle(s, P.ROCK_DARK, (int(x + ox + 1), int(y + oy + 2)), r)
            pygame.draw.circle(s, P.ROCK, (int(x + ox), int(y + oy)), r - 1)
            pygame.draw.circle(s, P.SAND_LIGHT, (int(x + ox - r // 3), int(y + oy - r // 3)), 1)


def goo_splat(rng, radius, flying=False):
    radius = max(3, int(radius * 0.8))
    size = radius * 3 + 4
    s = canvas(size, size)
    c = size // 2
    main, dark = (P.GOO_DARK, (40, 80, 30)) if not flying else (P.HIVE_PURPLE_DARK, P.CREEP_DARK)
    for _ in range(radius + 3):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(radius * 0.5, radius * 1.4)
        pygame.draw.circle(s, (*dark, 140), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), 1)
    pygame.draw.circle(s, (*dark, 130), (c, c), max(2, radius - 1))
    pygame.draw.circle(s, (*main, 130), (c - 1, c - 1), max(1, radius - 3))
    return s


def mineral_icon():
    s = canvas(8, 9)
    pygame.draw.polygon(s, P.MINERAL, [(4, 0), (7, 3), (6, 8), (2, 8), (1, 3)])
    pygame.draw.line(s, P.CRYO_LIGHT, (3, 2), (3, 6))
    return outline(s)


def heart_icon():
    s = canvas(9, 8)
    pygame.draw.rect(s, P.STEEL, (0, 0, 9, 8))
    pygame.draw.rect(s, P.RED, (3, 1, 3, 6))
    pygame.draw.rect(s, P.RED, (1, 3, 7, 2))
    return outline(s)


class SpriteBank:
    """Builds every sprite once and serves rotated, animated frames."""

    def __init__(self):
        self.enemies = {}
        for kind, (fn, frames) in ENEMY_DRAWERS.items():
            self.enemies[kind] = [rotations(fn(f)) for f in range(frames)]
        self.flash = {kind: [[pygame.mask.from_surface(img).to_surface(setcolor=P.WHITE, unsetcolor=(0, 0, 0, 0))
                              for img in frame] for frame in frames]
                      for kind, frames in self.enemies.items()}
        self.mound = [burrow_mound(f) for f in range(4)]
        self.tower_bases = {k: [b(t) for t in range(3)] for k, (b, _) in TOWER_DRAWERS.items()}
        self.turrets = {k: [rotations(t(tier)) for tier in range(3)] for k, (_, t) in TOWER_DRAWERS.items()}
        self.pad = pad()
        self.core = [command_core(False), command_core(True)]
        self.mineral = mineral_icon()
        self.heart = heart_icon()

    def enemy(self, kind, age, angle, flash=False):
        frames = (self.flash if flash else self.enemies)[kind]
        frame = frames[int(age * 8) % len(frames)]
        return frame[facing_index(angle)]

    def turret(self, kind, tier, angle):
        return self.turrets[kind][tier][facing_index(angle)]

    def icon(self, kind, tier=0):
        """A tower's base with its turret on top, facing right, for buttons and the portrait."""
        base = self.tower_bases[kind][tier]
        turret = self.turrets[kind][tier][0]
        s = base.copy()
        s.blit(turret, turret.get_rect(center=s.get_rect().center))
        return s
