"""OGC web services of Geobasis NRW for direct use in QGIS & co."""

from __future__ import annotations

_W = "https://www.wms.nrw.de/geobasis/"

SERVICES: list[dict[str, str]] = [
    {"id": "dop", "typ": "WMS", "titel": "Digitale Orthophotos (aktuell)", "url": _W + "wms_nw_dop"},
    {"id": "dop-hist", "typ": "WMS", "titel": "Historische Orthophotos (alle Jahrgänge)",
     "url": _W + "wms_nw_hist_dop"},
    {"id": "idop", "typ": "WMS", "titel": "InVeKoS-Orthophotos", "url": _W + "wms_nw_idop"},
    {"id": "vdop", "typ": "WMS", "titel": "Vorläufige Orthophotos (vDOP)", "url": _W + "wms_nw_vdop"},
    {"id": "alkis", "typ": "WMS", "titel": "Liegenschaftskataster ALKIS", "url": _W + "wms_nw_alkis"},
    {"id": "abk", "typ": "WMS", "titel": "Amtliche Basiskarte", "url": _W + "wms_nw_abk"},
    {"id": "dtk", "typ": "WMS", "titel": "Digitale Topographische Karten", "url": _W + "wms_nw_dtk"},
    {"id": "dgk5", "typ": "WMS", "titel": "Deutsche Grundkarte 1:5 000", "url": _W + "wms_nw_dgk5"},
    {"id": "dgm-schummerung", "typ": "WMS", "titel": "Geländeschummerung (DGM)",
     "url": _W + "wms_nw_dgm-schummerung"},
    {"id": "ndom", "typ": "WMS", "titel": "Normalisiertes Oberflächenmodell", "url": _W + "wms_nw_ndom"},
    {"id": "dvg", "typ": "WMS", "titel": "Verwaltungsgrenzen", "url": _W + "wms_nw_dvg"},
    {"id": "alkis-wfs", "typ": "WFS", "titel": "ALKIS vereinfacht (Flurstücke, Gebäude, Nutzung)",
     "url": "https://www.wfs.nrw.de/geobasis/wfs_nw_alkis_vereinfacht"},
    {"id": "dvg-wfs", "typ": "WFS", "titel": "Verwaltungsgrenzen",
     "url": "https://www.wfs.nrw.de/geobasis/wfs_nw_dvg"},
]
