"""Build the phone/browser version of Void Siege with pygbag.

    python -m void_siege.build_web

Output lands in build/voidsiege/build/web/ (index.html + the packed game).
Upload that folder to any static host (GitHub Pages, itch.io) and open it on a phone.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "build" / "voidsiege"

MAIN = '''import asyncio

from void_siege.game import Game


async def main():
    await Game().run()


asyncio.run(main())
'''


def assemble():
    if APP.exists():
        shutil.rmtree(APP)
    APP.mkdir(parents=True)
    shutil.copytree(ROOT / "void_siege", APP / "void_siege",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc", "build_web.py", "README.md",
                                                  "requirements.txt"))
    (APP / "main.py").write_text(MAIN, encoding="utf-8")
    return APP


def main():
    app = assemble()
    cmd = [sys.executable, "-m", "pygbag", "--build", "--archive", "--ume_block", "0",
           "--title", "Void Siege", "--app_name", "voidsiege", str(app)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    web = app / "build" / "web"
    if not (web / "index.html").exists():
        sys.exit(f"pygbag did not produce {web / 'index.html'}")
    print(f"Web build ready: {web}")


if __name__ == "__main__":
    main()
