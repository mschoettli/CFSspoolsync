import math


def grams_from_mm(length_mm: float, diameter_mm: float, density: float) -> float:
    if length_mm <= 0 or diameter_mm <= 0 or density <= 0:
        return 0.0
    radius_cm = (diameter_mm / 2.0) / 10.0
    length_cm = length_mm / 10.0
    return math.pi * radius_cm**2 * length_cm * density
