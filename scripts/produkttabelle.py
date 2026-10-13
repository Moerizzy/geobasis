"""Erzeugt docs/produkte.md mit Dateizahlen und Größen direkt aus den Länderkatalogen.

Aufruf: python scripts/produkttabelle.py > docs/produkte.md
"""

from __future__ import annotations

import datetime

from geobasis import LAENDER
from geobasis.models import format_size

ART = {"tiles": "Kacheln", "admin": "je Kreis/Bezirk", "single": "landesweit", "wfs": "Ausschnitt (WFS)"}


def main() -> None:
    print("# Produkte\n")
    print(f"Stand der Zahlen: {datetime.date.today():%d.%m.%Y}, erzeugt mit "
          "`python scripts/produkttabelle.py`. Wo „–“ steht, fragt geobasis den Katalog "
          "gezielt für das gewünschte Gebiet ab, statt ihn ganz aufzulisten.\n")
    for lnd in LAENDER.values():
        print(f"# {lnd.name}\n")
        print(f"Lizenz: {lnd.license}. Namensnennung: „{lnd.attribution}“.\n")
        for cat in lnd.categories():
            print(f"## {cat}\n")
            print("| ID | Titel | Art | Format | Dateien | Gesamtgröße |")
            print("|---|---|---|---|---:|---:|")
            for p in lnd.products():
                if p.category != cat:
                    continue
                if p.kind == "wfs":
                    n, size = "–", "je nach Gebiet"
                elif p.yearly:
                    ys = p.years()
                    n, size = f"{len(ys)} Jahrgänge ({ys[0]}–{ys[-1]})", "–"
                elif not p.enumerable:
                    n, size = "–", "–"
                else:
                    sel = p.find(None, with_meta=False)
                    n, size = f"{len(sel):,}".replace(",", "."), format_size(sel.total_size)
                print(f"| `{p.id}` | {p.title} | {ART[p.kind]} | {p.format} | {n} | {size} |")
            print()


if __name__ == "__main__":
    main()
