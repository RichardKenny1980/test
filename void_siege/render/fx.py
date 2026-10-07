"""Juice: particles, floating numbers, beams, explosion rings, screen shake and radio chatter."""
import math
import random

import pygame

from . import palette as P


class Effects:
    def __init__(self, font):
        self.font = font
        self.rng = random.Random()
        self.particles = []   # [x, y, vx, vy, life, max_life, color, size, gravity]
        self.texts = []       # [text surface, x, y, life]
        self.beams = []       # [points, life]
        self.rings = []       # [x, y, radius, life, max_life, color]
        self.flashes = []     # [x, y, angle, life, size]
        self.shake = 0.0
        self.chatter = []     # [text, life]

    # ---- spawners ------------------------------------------------------------

    def burst(self, x, y, color, count=8, speed=40, life=0.4, size=1, gravity=0.0, spread=math.pi * 2, angle=0.0):
        for _ in range(count):
            a = angle + self.rng.uniform(-spread / 2, spread / 2)
            v = self.rng.uniform(speed * 0.3, speed)
            lt = self.rng.uniform(life * 0.5, life)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v, lt, lt, color, size, gravity])

    def float_text(self, text, x, y, color):
        surf = self.font.render(text, False, color)
        self.texts.append([surf, x - surf.get_width() / 2, y, 0.9])

    def say(self, text, seconds=3.0):
        self.chatter.append([text, seconds])
        del self.chatter[:-3]

    def add_shake(self, amount):
        self.shake = min(6.0, self.shake + amount)

    # ---- world events ------------------------------------------------------------

    def handle(self, name, d, decals, sprites_rng, splat):
        if name == "fire":
            if d["kind"] == "bunker":
                self.flashes.append([d["x"], d["y"], d["angle"], 0.05, 3 + d["tier"]])
                self.burst(d["x"], d["y"], P.HAZARD, count=2, speed=60, life=0.12, angle=d["angle"], spread=0.8)
            elif d["kind"] == "mortar":
                self.flashes.append([d["x"], d["y"], d["angle"], 0.1, 6])
                self.burst(d["x"], d["y"], P.STEEL_LIGHT, count=6, speed=25, life=0.5, angle=d["angle"], spread=1.2)
                self.add_shake(0.6)
            elif d["kind"] == "missile":
                self.burst(d["x"], d["y"], P.STEEL_LIGHT, count=4, speed=20, life=0.4)
        elif name == "beam":
            self.beams.append([d["points"], 0.12])
            for x, y in d["points"][1:]:
                self.burst(x, y, P.CRYO_LIGHT, count=4, speed=25, life=0.35)
        elif name == "hit":
            color = P.FIRE if d["kind"] == "missile" else P.FLASH
            self.burst(d["x"], d["y"], color, count=5 if d["kind"] == "missile" else 3, speed=45, life=0.25)
            if d["kind"] == "missile":
                self.rings.append([d["x"], d["y"], 8, 0.25, 0.25, P.FIRE])
        elif name == "explode":
            r = d["radius"]
            self.rings.append([d["x"], d["y"], r, 0.35, 0.35, P.FIRE])
            self.burst(d["x"], d["y"], P.FIRE, count=18, speed=r * 2.5, life=0.5, size=2)
            self.burst(d["x"], d["y"], P.FIRE_DARK, count=10, speed=r * 1.5, life=0.7, size=2)
            self.burst(d["x"], d["y"], P.ROCK_DARK, count=8, speed=50, life=0.7, gravity=120)
            self.add_shake(1.5)
            decals.blit(scorch(sprites_rng, r), (d["x"] - r, d["y"] - r))
        elif name == "death":
            color = P.HIVE_PURPLE if d["flying"] else P.GOO
            self.burst(d["x"], d["y"], color, count=6 + d["radius"], speed=55, life=0.5, size=2, gravity=60)
            self.burst(d["x"], d["y"], P.TOXIC, count=4, speed=30, life=0.4)
            s = splat(sprites_rng, d["radius"], d["flying"])
            decals.blit(s, s.get_rect(center=(int(d["x"]), int(d["y"]))))
            self.float_text(f"+{d['amount']}", d["x"], d["y"] - 8, P.MINERAL)
            if d["kind"] == "hive_titan":
                self.add_shake(6)
                for _ in range(4):
                    self.rings.append([d["x"], d["y"], 40, 0.6, 0.6, P.TOXIC])
                self.say("Titan down! Hell of a shot, Commander.")
        elif name == "boss_hit":
            self.add_shake(0.25)
        elif name == "leak":
            self.add_shake(2.0 + d["amount"] * 0.4)
            self.burst(d["x"], d["y"], P.RED, count=12, speed=50, life=0.5, size=2)
            self.float_text(f"-{d['amount']}", d["x"], d["y"] - 22, P.RED)
        elif name == "build":
            self.burst(d["x"], d["y"], P.SAND_LIGHT, count=14, speed=40, life=0.5, size=2)
        elif name == "upgrade":
            self.rings.append([d["x"], d["y"], 18, 0.4, 0.4, P.HAZARD])
            self.burst(d["x"], d["y"], P.HAZARD, count=12, speed=50, life=0.4)
        elif name == "sell":
            self.float_text(f"+{d['amount']}", d["x"], d["y"] - 10, P.MINERAL)
            self.burst(d["x"], d["y"], P.STEEL_LIGHT, count=10, speed=40, life=0.4)
        elif name == "brood":
            self.burst(d["x"], d["y"], P.GOO, count=6, speed=30, life=0.4)
        elif name == "wave":
            if d["boss"]:
                self.say("WARNING: massive bio-signature inbound!")
                self.add_shake(3)
            else:
                self.say(RADIO_LINES[(d["number"] - 1) % len(RADIO_LINES)])
            if d["bonus"]:
                self.say(f"Wave bonus: +{d['bonus']} minerals")

    # ---- update & draw ------------------------------------------------------------

    def update(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            p[2] *= 0.96
            p[3] *= 0.96
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0][-600:]
        for t in self.texts:
            t[2] -= 18 * dt
            t[3] -= dt
        self.texts = [t for t in self.texts if t[3] > 0]
        for group in (self.beams, self.rings, self.flashes):
            for item in group:
                item[3 if group is not self.beams else 1] -= dt
        self.beams = [b for b in self.beams if b[1] > 0]
        self.rings = [r for r in self.rings if r[3] > 0]
        self.flashes = [f for f in self.flashes if f[3] > 0]
        self.shake = max(0.0, self.shake - dt * 12)

    def update_chatter(self, real_dt):
        for c in self.chatter:
            c[1] -= real_dt
        self.chatter = [c for c in self.chatter if c[1] > 0]

    def shake_offset(self):
        if self.shake <= 0.05:
            return 0, 0
        m = round(self.shake)
        return self.rng.randint(-m, m), self.rng.randint(-m, m)

    def draw(self, surf, ox=0, oy=0):
        for points, life in self.beams:
            pts = [(x + ox, y + oy) for x, y in points]
            pygame.draw.lines(surf, P.TEAM_BLUE, False, pts, 3)
            pygame.draw.lines(surf, P.CRYO_LIGHT, False, pts, 1)
        for x, y, r, life, max_life, color in self.rings:
            t = 1 - life / max_life
            pygame.draw.circle(surf, color, (int(x + ox), int(y + oy)), max(1, int(r * (0.3 + t))), 1)
        for x, y, angle, life, size in self.flashes:
            cx, cy = x + ox + math.cos(angle) * 2, y + oy + math.sin(angle) * 2
            pygame.draw.circle(surf, P.FIRE, (int(cx), int(cy)), size)
            pygame.draw.circle(surf, P.FLASH, (int(cx), int(cy)), max(1, size - 2))
        for x, y, _, _, life, max_life, color, size, _ in self.particles:
            if life / max_life < 0.3 and size > 1:
                size -= 1
            surf.fill(color, (int(x + ox), int(y + oy), size, size))
        for s, x, y, life in self.texts:
            s.set_alpha(int(255 * min(1.0, life * 2.5)))
            surf.blit(s, (int(x + ox), int(y + oy)))


def scorch(rng, radius):
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for _ in range(radius):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, radius * 0.8)
        pygame.draw.circle(s, (40, 26, 18, 35), (int(radius + math.cos(a) * d), int(radius + math.sin(a) * d)),
                           rng.randrange(2, 5))
    return s


RADIO_LINES = [
    "Contacts on the ridge. Weapons free.",
    "More of 'em coming out of the creep!",
    "Armored bugs. Small arms won't cut it.",
    "Fliers incoming! Get missiles up!",
    "They're testing the line, hold steady.",
    "Seismic readings... they're under the sand!",
    "Big swarm. Keep that road covered.",
    "Air and ground together. Stay sharp.",
    "This is the push. Everything you've got!",
]
