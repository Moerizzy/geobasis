"""Erzeugt docs/produkte.md mit Dateizahlen und Größen direkt aus dem Portal.

Aufruf: python scripts/produkttabelle.py > docs/produkte.md
"""

from __future__ import annotations

import datetime

from geobasis import nrw
from geobasis.models import format_size

ART = {"tiles": "Kacheln", "admin": "je Kreis/Bezirk", "single": "landesweit", "wfs": "Ausschnitt (WFS)"}


def main() -> None:
    print("# Produkte für Nordrhein-Westfalen\n")
    print(f"Stand der Zahlen: {datetime.date.today():%d.%m.%Y}, erzeugt mit "
          "`python scripts/produkttabelle.py`. Alle Daten: Geobasis NRW, "
          "Datenlizenz Deutschland – Zero – Version 2.0.\n")
    for cat in nrw.categories():
        print(f"## {cat}\n")
        print("| ID | Titel | Art | Format | Dateien | Gesamtgröße |")
        print("|---|---|---|---|---:|---:|")
        for p in nrw.products(cat):
            if p.category != cat:
                continue
            if p.kind == "wfs":
                n, size = "–", "je nach Gebiet"
            elif p.yearly:
                ys = p.years()
                n, size = f"{len(ys)} Jahrgänge ({ys[0]}–{ys[-1]})", "–"
            else:
                sel = p.find(None, with_meta=False)
                n, size = f"{len(sel):,}".replace(",", "."), format_size(sel.total_size)
            print(f"| `{p.id}` | {p.title} | {ART[p.kind]} | {p.format} | {n} | {size} |")
        print()


if __name__ == "__main__":
    main()
