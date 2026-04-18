"""
Lookup-Tabelle für Creality CFS Material-Codes.

Das CFS liest per RFID einen 6-stelligen Code vom Spulenchip. Die ersten
drei Stellen sind ein Hersteller-Präfix, die restlichen drei ein
Material-/Varianten-Code. Diese Mappings basieren auf beobachteten Werten
der K2-Combo-Firmware und der Creality-Dokumentation.

Unbekannte Codes werden als Roh-Code zurückgegeben damit sie im UI
sichtbar sind und ergänzt werden können.
"""

# Die gängigsten Codes aus der beobachteten K2-Firmware
MATERIAL_CODES: dict[str, dict] = {
    # Creality Original (10xxxx)
    "100001": {"manufacturer": "Creality", "material": "PLA",        "nozzle": 210, "bed": 60},
    "100002": {"manufacturer": "Creality", "material": "PLA+",       "nozzle": 215, "bed": 60},
    "100003": {"manufacturer": "Creality", "material": "PETG",       "nozzle": 240, "bed": 80},
    "100004": {"manufacturer": "Creality", "material": "ABS",        "nozzle": 240, "bed": 100},
    "100005": {"manufacturer": "Creality", "material": "TPU",        "nozzle": 220, "bed": 50},
    "100006": {"manufacturer": "Creality", "material": "ASA",        "nozzle": 250, "bed": 100},
    "100007": {"manufacturer": "Creality", "material": "PC",         "nozzle": 270, "bed": 110},
    "100008": {"manufacturer": "Creality", "material": "Nylon",      "nozzle": 260, "bed": 90},

    # Creality Hyper-Serie (104xxx)
    "104001": {"manufacturer": "Creality", "material": "Hyper PLA",  "nozzle": 210, "bed": 60},
    "104002": {"manufacturer": "Creality", "material": "Hyper PLA+", "nozzle": 215, "bed": 60},
    "104003": {"manufacturer": "Creality", "material": "Hyper PETG", "nozzle": 240, "bed": 80},
    "104004": {"manufacturer": "Creality", "material": "Hyper ABS",  "nozzle": 240, "bed": 100},

    # Creality CR-Serie / Ender (108xxx)
    "108001": {"manufacturer": "Creality", "material": "CR-PLA",     "nozzle": 210, "bed": 60},
    "108002": {"manufacturer": "Creality", "material": "Ender PLA",  "nozzle": 210, "bed": 60},
    "108003": {"manufacturer": "Creality", "material": "Ender PETG", "nozzle": 240, "bed": 80},
}


def lookup_material(code: str) -> dict | None:
    """
    Gibt das Mapping für einen Material-Code zurück, oder None falls unbekannt.

    Bei unbekannten Codes können Nutzer den Eintrag selbst anlegen — bis
    dahin zeigt das UI den Rohcode zusammen mit 'Unbekannte Spule' an.
    """
    if not code or code in ("-1", "None", ""):
        return None
    return MATERIAL_CODES.get(code)


def parse_color(raw: str) -> str:
    """
    CFS liefert Farben als 7-stelligen Hex-Wert mit führender '0':
    '0F7B30F' -> '#F7B30F'. Bei ungültigen Werten fällt auf ein neutrales
    Grau zurück damit das UI nie crashed.
    """
    if not raw or raw in ("-1", "None", ""):
        return "#6b7280"
    # Führendes '0' abschneiden, auf 6 Stellen padden
    hex_part = raw.lstrip("0") or "000000"
    hex_part = hex_part.zfill(6)[:6].upper()
    # Basic hex validation
    try:
        int(hex_part, 16)
    except ValueError:
        return "#6b7280"
    return f"#{hex_part}"
