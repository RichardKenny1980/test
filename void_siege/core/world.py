import math

from .data import load_all
from .entities import Enemy, Projectile, Tower
from .grid import CELL, Grid
from .path import Path
from .targeting import choose_target

TICK = 1.0 / 60.0


class WaveManager:
    """Spawns enemy groups for each wave and runs the countdown between waves."""

    def __init__(self, waves, gap):
        self.waves = waves
        self.gap = gap
        self.index = -1  # index of the most recently started wave
        self.groups = []
        self.countdown = None  # seconds until the next wave auto-starts; None = wait for player

    @property
    def total(self):
        return len(self.waves)

    @property
    def spawning(self):
        return any(g["left"] > 0 for g in self.groups)

    @property
    def has_next(self):
        return self.index + 1 < self.total

    @property
    def can_call(self):
        return self.has_next and not self.spawning

    def start_next(self):
        self.index += 1
        self.countdown = None
        self.groups = [
            {"enemy": g["enemy"], "left": g["count"], "interval": g["interval"], "timer": g.get("delay", 0.0)}
            for g in self.waves[self.index]
        ]

    def preview(self):
        """Enemy kinds and counts in the next wave, for the incoming-wave icons."""
        if not self.has_next:
            return []
        counts = {}
        for g in self.waves[self.index + 1]:
            counts[g["enemy"]] = counts.get(g["enemy"], 0) + g["count"]
        return list(counts.items())

    def update(self, dt):
        """Advance spawn timers. Returns a list of enemy kinds to spawn this tick."""
        spawns = []
        for g in self.groups:
            if g["left"] <= 0:
                continue
            g["timer"] -= dt
            while g["left"] > 0 and g["timer"] <= 0:
                spawns.append(g["enemy"])
                g["left"] -= 1
                g["timer"] += g["interval"]
        if self.index >= 0 and not self.spawning and self.has_next and self.countdown is None:
            self.countdown = float(self.gap)
        if self.countdown is not None:
            self.countdown -= dt
        return spawns


def shift_map(m, dx, dy=0):
    """Move a map by (dx, dy) to centre it on a bigger screen. A path that starts off the left edge
    still starts there, so enemies keep walking in from the edge of the screen."""
    m = dict(m)
    if "path" in m:
        path = [[x + dx, y + dy] for x, y in m["path"]]
        if m["path"][0][0] < 0:
            path[0][0] = m["path"][0][0]
        m["path"] = path
    if "spawn" in m:
        x, y = m["spawn"]
        m["spawn"] = [x if x < 0 else x + dx, y + dy]
    m["pads"] = [[x + dx, y + dy] for x, y in m.get("pads", [])]
    m["core"] = [m["core"][0] + dx, m["core"][1] + dy]
    return m


def _overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class World:
    """The whole battle simulation. Call update() at a fixed tick rate."""

    def __init__(self, map_name="map01", offset_x=0, offset_y=0, reserved=()):
        """`reserved` lists screen rects (x, y, w, h) kept free of turrets, such as the HUD buttons."""
        self.tower_specs, self.enemy_specs, self.map = load_all(map_name)
        self.map_name = map_name
        self.kind = self.map.get("kind", "pads")  # pads | open | maze
        if offset_x or offset_y:
            self.map = shift_map(self.map, offset_x, offset_y)
        self.core = tuple(self.map["core"])
        self.grid = None
        if self.kind == "pads":
            self.pads = [tuple(p) for p in self.map["pads"]]
        else:
            self.grid = Grid(self.map.get("cols", 32), self.map.get("rows", 14), (offset_x, offset_y),
                             self.map.get("rocks", ()))
        if self.kind == "maze":
            self.entry = self.grid.cell_at(*self.map["spawn"])
            self.core_cell = self.grid.cell_at(*self.core)
            self.walls = set()
            self.path = self._maze_path(self.entry, self.grid.distances(self.core_cell, self.walls),
                                        self.map["spawn"])
        else:
            self.path = Path(self.map["path"])
        self.spawn_point = self.path.points[0]
        self.flight_path = Path([self.spawn_point, self.core])
        if self.grid is not None:
            self.pad_cells = [c for c in self.grid.cells() if self._buildable(c, reserved)]
            self.pads = [self.grid.center(c) for c in self.pad_cells]
            self.cell_pad = {c: i for i, c in enumerate(self.pad_cells)}
        self.hp_scale = self.map.get("hp_scale", 1.0)
        self.minerals = self.map["start_minerals"]
        self.core_hp = self.max_core_hp = self.map["core_hp"]
        self.waves = WaveManager(self.map["waves"], self.map.get("wave_gap", 20))
        self.enemies = []
        self.towers = {}  # pad index -> Tower
        self.projectiles = []
        self.events = []  # (name, data dict) consumed by the renderer each frame
        self.time = 0.0
        self.kills = 0

    # ---- player actions -------------------------------------------------

    def build_cost(self, kind):
        return self.tower_specs[kind]["tiers"][0]["cost"]

    def _buildable(self, cell, reserved):
        g = self.grid
        rect = g.rect(cell)
        cx, cy = self.core
        if cell in g.rocks or _overlaps(rect, (cx - 30, cy - 30, 60, 60)):
            return False
        if any(_overlaps(rect, r) for r in reserved):
            return False
        if self.kind == "maze":
            return cell != self.entry
        x, y = g.center(cell)
        return self.path.distance_to(x, y) >= CELL / 2 + 14  # clear of the 28px road

    def blocks_route(self, pad):
        """Maze levels: why a turret can't go on this pad right now, or None if it can.
        "occupied": a walker is standing there. "sealed": it would cut the Hive off from the core
        or trap a walker."""
        if self.kind != "maze" or pad in self.towers:
            return None
        cell = self.pad_cells[pad]
        g = self.grid
        cx, cy = g.center(cell)
        for e in self.enemies:
            if not e.flying and abs(e.x - cx) < CELL / 2 + e.radius and abs(e.y - cy) < CELL / 2 + e.radius:
                return "occupied"
        dist = g.distances(self.core_cell, self.walls | {cell})
        if self.entry not in dist or any(g.cell_at(e.x, e.y) not in dist for e in self.enemies if not e.flying):
            return "sealed"
        return None

    def _maze_path(self, start, dist, from_point):
        return Path([tuple(from_point)] + self.grid.points(self.grid.route(start, dist)))

    def _reroute(self):
        """Maze levels: after a turret goes up or comes down, every walker takes the new shortest way."""
        g = self.grid
        self.walls = {self.pad_cells[p] for p in self.towers}
        dist = g.distances(self.core_cell, self.walls)
        self.path = self._maze_path(self.entry, dist, self.spawn_point)
        for e in self.enemies:
            if e.flying:
                continue
            here = (e.x, e.y)
            cells = g.route(g.cell_at(*here), dist)
            pts = [here] + g.points(cells) if cells else [here, self.core]
            e.path, e.distance = Path(pts), 0.0
            e.update(0.0)
        self._event("reroute")

    def build(self, kind, pad):
        if pad in self.towers or self.minerals < self.build_cost(kind) or self.blocks_route(pad):
            return None
        x, y = self.pads[pad]
        tower = Tower(kind, self.tower_specs[kind], x, y, pad)
        self.minerals -= tower.spent
        self.towers[pad] = tower
        self._event("build", x=x, y=y)
        if self.kind == "maze":
            self._reroute()
        return tower

    def upgrade(self, tower):
        cost = tower.upgrade_cost
        if cost is None or self.minerals < cost:
            return False
        self.minerals -= cost
        tower.spent += cost
        tower.tier += 1
        self._event("upgrade", x=tower.x, y=tower.y)
        return True

    def sell(self, tower):
        self.minerals += tower.sell_value
        del self.towers[tower.pad]
        self._event("sell", x=tower.x, y=tower.y, amount=tower.sell_value)
        if self.kind == "maze":
            self._reroute()

    def call_wave(self):
        """Start the next wave now. Calling early pays a bonus for the time skipped."""
        if not self.waves.can_call:
            return 0
        bonus = 0
        if self.waves.countdown is not None:
            bonus = max(0, int(self.waves.countdown))
        if self.waves.index >= 0:
            bonus += self.map.get("wave_bonus", 0) + self.map.get("wave_bonus_step", 0) * self.waves.index
        self.minerals += bonus
        self.waves.start_next()
        self._event("wave", number=self.waves.index + 1, bonus=bonus,
                    boss=any(self.enemy_specs[g["enemy"]].get("boss") for g in self.waves.groups))
        return bonus

    # ---- state ------------------------------------------------------------

    @property
    def won(self):
        return (self.core_hp > 0 and not self.waves.has_next and not self.waves.spawning
                and self.waves.index >= 0 and not self.enemies)

    @property
    def lost(self):
        return self.core_hp <= 0

    @property
    def over(self):
        return self.won or self.lost

    @property
    def stars(self):
        if not self.won:
            return 0
        ratio = self.core_hp / self.max_core_hp
        return 3 if ratio >= 0.9 else 2 if ratio >= 0.5 else 1

    def pad_at(self, x, y, radius=12):
        for i, (px, py) in enumerate(self.pads):
            if abs(x - px) <= radius and abs(y - py) <= radius:
                return i
        return None

    # ---- simulation -------------------------------------------------------

    def spawn(self, kind, distance=0.0, path=None):
        stats = self.enemy_specs[kind]
        if path is None:
            path = self.flight_path if stats.get("flying") else self.path
        enemy = Enemy(kind, stats, path, distance=distance, hp=stats["hp"] * self.hp_scale)
        self.enemies.append(enemy)
        return enemy

    def update(self, dt=TICK):
        if self.over:
            return
        self.time += dt

        for kind in self.waves.update(dt):
            self.spawn(kind)
        if self.waves.countdown is not None and self.waves.countdown <= 0:
            self.call_wave()

        self._update_enemies(dt)
        self._update_detection()
        self._update_towers(dt)
        self._update_projectiles(dt)

    def _update_enemies(self, dt):
        for enemy in list(self.enemies):
            enemy.update(dt)
            if enemy.stats.get("spawns"):
                enemy.spawn_timer -= dt
                if enemy.spawn_timer <= 0:
                    enemy.spawn_timer += enemy.stats["spawn_every"]
                    child = self.spawn(enemy.stats["spawns"], distance=max(0.0, enemy.distance - 6), path=enemy.path)
                    self._event("brood", x=child.x, y=child.y)
            if enemy.reached_end:
                enemy.alive = False
                self.enemies.remove(enemy)
                self.core_hp = max(0, self.core_hp - enemy.stats["leak"])
                self._event("leak", x=self.core[0], y=self.core[1], amount=enemy.stats["leak"])

    def _update_detection(self):
        detectors = [t for t in self.towers.values() if t.detector]
        for enemy in self.enemies:
            if enemy.burrowed:
                enemy.detected = any(
                    math.hypot(enemy.x - t.x, enemy.y - t.y) <= t.range + enemy.radius for t in detectors)

    def _update_towers(self, dt):
        for tower in self.towers.values():
            tower.cooldown = max(0.0, tower.cooldown - dt)
            tower.recoil = max(0.0, tower.recoil - dt)
            target = choose_target(tower, self.enemies)
            if target is None:
                continue
            tower.angle = math.atan2(target.y - tower.y, target.x - tower.x)
            if tower.cooldown > 0:
                continue
            tower.cooldown = tower.stats["cooldown"]
            tower.recoil = 0.12
            self._fire(tower, target)

    def _fire(self, tower, target):
        stats, spec = tower.stats, tower.spec
        muzzle_x = tower.x + math.cos(tower.angle) * 10
        muzzle_y = tower.y + math.sin(tower.angle) * 10
        self._event("fire", kind=tower.kind, x=muzzle_x, y=muzzle_y, angle=tower.angle, tier=tower.tier)
        if spec["projectile"] == "beam":
            hit = [target]
            for _ in range(stats.get("chain", 0)):
                nxt = min(
                    (e for e in self.enemies if e.targetable and e not in hit and tower.can_hit(e)
                     and math.hypot(e.x - hit[-1].x, e.y - hit[-1].y) <= 40),
                    key=lambda e: math.hypot(e.x - hit[-1].x, e.y - hit[-1].y), default=None)
                if nxt is None:
                    break
                hit.append(nxt)
            points = [(muzzle_x, muzzle_y)] + [(e.x, e.y) for e in hit]
            self._event("beam", points=points)
            for enemy in hit:
                enemy.apply_slow(stats["slow"], stats["slow_time"])
                self._damage(enemy, stats["damage"], spec.get("pierce", False))
            return
        self.projectiles.append(Projectile(
            kind=spec["projectile"], x=muzzle_x, y=muzzle_y, target=target, tx=target.x, ty=target.y,
            speed=spec["projectile_speed"], damage=stats["damage"], splash=stats.get("splash", 0.0),
            pierce=spec.get("pierce", False), targets=tuple(spec["targets"])))

    def _update_projectiles(self, dt):
        for p in list(self.projectiles):
            homing = p.kind in ("bullet", "missile")
            if homing and p.target.alive:
                p.tx, p.ty = p.target.x, p.target.y
            dx, dy = p.tx - p.x, p.ty - p.y
            dist = math.hypot(dx, dy)
            step = p.speed * dt
            if p.kind == "missile":
                p.trail.append((p.x, p.y))
                del p.trail[:-8]
            if dist > step:
                p.x += dx / dist * step
                p.y += dy / dist * step
                continue
            p.x, p.y = p.tx, p.ty
            p.alive = False
            self.projectiles.remove(p)
            if p.splash:
                self._event("explode", x=p.x, y=p.y, radius=p.splash)
                for enemy in list(self.enemies):
                    layer = "air" if enemy.flying else "ground"
                    if (layer in p.targets and enemy.alive
                            and math.hypot(enemy.x - p.x, enemy.y - p.y) <= p.splash + enemy.radius):
                        self._damage(enemy, p.damage, p.pierce)
            elif p.target.alive:
                self._event("hit", x=p.x, y=p.y, kind=p.kind)
                self._damage(p.target, p.damage, p.pierce)

    def _damage(self, enemy, amount, pierce):
        if not enemy.alive:
            return
        enemy.take_damage(amount, pierce)
        if enemy.boss:
            self._event("boss_hit", x=enemy.x, y=enemy.y)
        if not enemy.alive:
            self.enemies.remove(enemy)
            self.kills += 1
            reward = enemy.stats["reward"]
            self.minerals += reward
            self._event("death", x=enemy.x, y=enemy.y, kind=enemy.kind, radius=enemy.radius,
                        flying=enemy.flying, amount=reward)

    def _event(self, name, **data):
        self.events.append((name, data))

    def drain_events(self):
        events, self.events = self.events, []
        return events
