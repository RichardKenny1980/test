import math
from dataclasses import dataclass, field


@dataclass
class Enemy:
    kind: str
    stats: dict
    path: object
    distance: float = 0.0
    hp: float = 0.0
    slow: float = 0.0
    slow_timer: float = 0.0
    spawn_timer: float = 0.0
    detected: bool = False
    hit_flash: float = 0.0
    age: float = 0.0
    alive: bool = True
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0

    def __post_init__(self):
        if not self.hp:
            self.hp = self.stats["hp"]
        self.max_hp = self.stats["hp"]
        self.spawn_timer = self.stats.get("spawn_every", 0.0)
        self._update_position()

    @property
    def flying(self):
        return self.stats.get("flying", False)

    @property
    def burrowed(self):
        return self.stats.get("burrowed", False)

    @property
    def boss(self):
        return self.stats.get("boss", False)

    @property
    def radius(self):
        return self.stats["radius"]

    @property
    def targetable(self):
        return self.alive and (not self.burrowed or self.detected)

    @property
    def speed(self):
        return self.stats["speed"] * (1.0 - self.slow)

    def apply_slow(self, amount, duration):
        amount *= 1.0 - self.stats.get("slow_resist", 0.0)
        if amount >= self.slow:
            self.slow = amount
            self.slow_timer = max(self.slow_timer, duration)

    def take_damage(self, damage, pierce=False):
        """Apply damage after armor. Returns the damage actually dealt."""
        if not pierce:
            damage = max(damage - self.stats.get("armor", 0), damage * 0.25)
        self.hp -= damage
        self.hit_flash = 0.08
        if self.hp <= 0:
            self.alive = False
        return damage

    def update(self, dt):
        self.age += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow = 0.0
        self.distance += self.speed * dt
        self._update_position()

    def _update_position(self):
        self.x, self.y, self.heading = self.path.position(self.distance)

    @property
    def reached_end(self):
        return self.distance >= self.path.length


@dataclass
class Tower:
    kind: str
    spec: dict
    x: float
    y: float
    pad: int
    tier: int = 0
    cooldown: float = 0.0
    targeting: str = "first"
    angle: float = 0.0
    recoil: float = 0.0
    spent: int = 0

    TARGETING_MODES = ("first", "last", "strongest", "closest")

    def __post_init__(self):
        self.spent = self.spec["tiers"][0]["cost"]

    @property
    def stats(self):
        return self.spec["tiers"][self.tier]

    @property
    def range(self):
        return self.stats["range"]

    @property
    def max_tier(self):
        return len(self.spec["tiers"]) - 1

    @property
    def upgrade_cost(self):
        if self.tier >= self.max_tier:
            return None
        return self.spec["tiers"][self.tier + 1]["cost"]

    @property
    def sell_value(self):
        return int(self.spent * 0.7)

    @property
    def detector(self):
        return self.spec.get("detector", False)

    def can_hit(self, enemy):
        layer = "air" if enemy.flying else "ground"
        return layer in self.spec["targets"] and enemy.targetable

    def in_range(self, enemy):
        return math.hypot(enemy.x - self.x, enemy.y - self.y) <= self.range + enemy.radius

    def cycle_targeting(self):
        i = self.TARGETING_MODES.index(self.targeting)
        self.targeting = self.TARGETING_MODES[(i + 1) % len(self.TARGETING_MODES)]


@dataclass
class Projectile:
    kind: str
    x: float
    y: float
    target: object
    tx: float
    ty: float
    speed: float
    damage: float
    splash: float = 0.0
    pierce: bool = False
    targets: tuple = ("ground", "air")
    alive: bool = True
    trail: list = field(default_factory=list)
    start: tuple = (0.0, 0.0)

    def __post_init__(self):
        self.start = (self.x, self.y)
