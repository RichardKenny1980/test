# Void Siege

A tower defense game in Python with the chunky cartoon-space look of late-90s RTS games. Hold Dustfall Ridge and the colony's Command Core against 10 waves of the Skrell Hive.

## Run it

```bash
pip install -r void_siege/requirements.txt
python -m void_siege          # from the repository root
```

The game renders at 640×360 and scales to fit your window. Press **F11** for fullscreen.

## How to play

Enemies crawl out of the creep on the left and follow the road to your Command Core. Each one that gets through costs Core HP (the Hive Titan costs 10). Lose all 20 and the colony falls.

| Key | Action |
|---|---|
| 1-4 | Pick a tower, then click an empty pad (hold Shift to place several) |
| Click a tower | Select it to see its stats and range |
| U / S / T | Upgrade, sell (70% refund), or cycle targeting (First, Last, Strongest, Closest) |
| Space | Launch the next wave. Calling it early pays a mineral bonus |
| F | Game speed 1x / 2x / 3x |
| P or Esc | Pause |
| Right-click | Cancel |

### Towers
- **Autocannon Bunker**: cheap rapid fire, hits ground and air.
- **Siege Mortar**: slow armor-piercing splash, ground only.
- **Cryo Projector**: slows enemies. At Mk III the frost chains to nearby bugs.
- **Missile Turret**: heavy anti-air, and reveals burrowed enemies to every tower.

### The Hive
- **Skitterling**: fast swarmers. **Spine Brute**: slow and tough. **Carapace Crawler**: armored, so small guns barely scratch it.
- **Gloomwing**: flies straight at the core over the road. **Burrower**: invisible underground until a Missile Turret spots it.
- **Hive Titan**: the wave 10 boss. It's huge, shrugs off half of any slow and spawns Skitterlings as it walks.

You get 1-3 stars for winning, based on how much Core HP is left.

## Code layout

- `core/`: the simulation (path, towers, enemies, waves, economy). It never imports pygame, so it runs headless in tests.
- `render/`: procedural sprites (`art.py`), the battlefield (`field.py`), effects (`fx.py`) and the console HUD (`hud.py`).
- `data/`: tower, enemy, map and wave definitions in JSON. Balance changes go here.
- `game.py`: the window, main loop, menu and battle scenes.

## Tests

```bash
python -m pytest void_siege
```

`tests/autoplay.py` is a scripted player. The balance tests check that a sensible build wins with 3 stars, doing nothing loses, and spamming one tower type loses.
