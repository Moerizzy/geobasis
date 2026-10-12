# Mitmachen

Danke für dein Interesse! Fehlermeldungen, Wünsche und Pull Requests sind willkommen.

- **Fehler melden:** Bitte den genauen Befehl, die Ausgabe und `geobasis --version` angeben.
- **Neue Produkte:** Ein Eintrag in `src/geobasis/laender/nrw/products.py` genügt
  oft. Bitte einen Online-Test mitliefern (`tests/test_online.py` deckt jedes
  Produkt automatisch ab) und `docs/produkte.md` mit
  `python scripts/produkttabelle.py > docs/produkte.md` erneuern.
- **Neue Länder:** siehe [docs/architektur.md](docs/architektur.md).
- **Stil:** `ruff check src tests` muss sauber sein, `pytest` grün. Code und
  Kommentare auf Englisch, Texte für Nutzerinnen und Nutzer auf Deutsch.
- **Schonender Umgang mit den Servern:** Standardmäßig höchstens 4 parallele
  Downloads; Verzeichnisse werden zwischengespeichert. Bitte beibehalten.

Mit einem Beitrag stimmst du zu, dass er unter der MIT-Lizenz des Projekts steht.
