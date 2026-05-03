"""
main.py
=======
Entry point terpusat untuk semua ekspresi robot face.

Usage:
    python main.py [expression]

Ekspresi yang tersedia:
    happy     - Mulut senyum lebar (default)
    happier   - Senyum + pipi memerah + mata bintang
    sad       - Mulut cemberut / frown
    shock     - Mulut oval oval mengejutkan (squash & stretch)
    cry       - Mata berair + aliran air mata + mulut tangis
    shy       - Mulut 'w' + pipi memerah + mata bintang
    talking   - Mulut buka-tutup (tekan SPASI toggle)
    load      - Mata berlapis/bergaya + mulut oval

Contoh:
    python main.py cry
    python main.py happy
    python main.py talking
"""

import sys
import os

# Tambah directory REFINEMENT ke path agar import dari core/ dan expressions/ bekerja
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expressions import happy, happier, sad, shock, cry, shy, talking, load

EXPRESSIONS = {
    "happy":   happy.run,
    "happier": happier.run,
    "sad":     sad.run,
    "shock":   shock.run,
    "cry":     cry.run,
    "shy":     shy.run,
    "talking": talking.run,
    "load":    load.run,
}

def main():
    expression = sys.argv[1].lower() if len(sys.argv) > 1 else "happy"

    if expression not in EXPRESSIONS:
        print(f"❌  Ekspresi '{expression}' tidak dikenal.")
        print(f"✅  Tersedia: {', '.join(EXPRESSIONS.keys())}")
        sys.exit(1)

    print(f"🤖  Menjalankan ekspresi: {expression}")
    EXPRESSIONS[expression]()


if __name__ == "__main__":
    main()
