# Void Siege

A tower defense game in Python with the chunky cartoon-space look of late-90s RTS games. Hold Dustfall Ridge and the colony's Command Core against 10 waves of the Skrell Hive.

## Play on a phone

Void Siege is built for phones. The pygame code is compiled for the browser with [pygbag](https://pypi.org/project/pygbag/) (Python running as WebAssembly), so it plays in Safari on iPhone or Chrome on Android with nothing to install. Hold the phone sideways.

- **Hosted:** every push to `main` publishes the game to GitHub Pages (`.github/workflows/void-siege-pages.yml`). This needs one-time setup: in the repo go to Settings > Pages > Source and pick "GitHub Actions". After that the game lives at `https://richardkenny1980.github.io/test/`. On the phone, use Share > Add to Home Screen to launch it like an app.
- **Every PR:** CI uploads the web build as a `void-siege-web` artifact.
- **Build it yourself:** `pip install pygbag && python -m void_siege.build_web`. To test on a phone on the same Wi-Fi, run `python -m pygbag build/voidsiege` and open `http://<your-computer-ip>:8000`.

## Play on desktop

```bash
pip install -r void_siege/requirements.txt
python -m void_siege          # from the repository root
```

The game renders at 640×360 and scales to fit your window. Press **F11** for fullscreen.

## How to play

Enemies crawl out of the creep on the left and follow the road to your Command Core. Each one that gets through costs Core HP (the Hive Titan costs 10). Lose all 20 and the colony falls.

Everything is a tap (or a click on desktop):

| Tap | What happens |
|---|---|
| An empty pad | A ring of the 4 turrets pops up. Tap one to see its stats and range, then tap it again to build |
| A turret | Ring with **Upgrade** (tap twice), **Aim** (cycles First, Last, Strongest, Nearest) and **Sell** (tap twice, 70% refund) |
| **WAVE** | Launch the next wave. Calling it early pays a mineral bonus |
| **SPEED** / **PAUSE** | 1x, 2x or 3x game speed, and pause |
| Anywhere else | Close the ring |

Desktop shortcuts: 1-4 build on the open pad, U upgrade, S sell, T aim, Space wave, F speed, P or Esc pause.

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
- `game.py`: the window, the async main loop (shared by desktop and browser), menu and battle scenes.
- `render/radial.py`: the tap-to-open ring menu.
- `build_web.py`: packages the game for phones and browsers with pygbag.

## Tests

```bash
python -m pytest void_siege
```

`tests/autoplay.py` is a scripted player. The balance tests check that a sensible build wins with 3 stars, doing nothing loses, and spamming one tower type loses.
