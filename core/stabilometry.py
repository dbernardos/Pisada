"""
Cálculos de estabilometria a partir da trajetória do centro de pressão (CoP).

Convenção das séries (iguais às guardadas em StabilometryResult.cop_*):
    x em mm, positivo para a DIREITA
    y em mm, positivo para a FRENTE (anterior)
    amostrados a `sample_rate_hz`
"""
import math

import numpy as np


def bbox_ellipse_area(x, y):
    """
    Área (mm²) da elipse inscrita no retângulo que envolve a trajetória.
    É a definição usada pelos relatórios clínicos de referência (π/4 · largura · altura).
    Para usar uma elipse de confiança estatística, troque apenas esta função.
    """
    width, height = extent(x), extent(y)
    return math.pi / 4 * width * height


def extent(values):
    """Amplitude total (máx - mín) de uma série, em mm."""
    values = np.asarray(values, dtype=float)
    return float(values.max() - values.min()) if values.size else 0.0


def path_length(x, y):
    """Comprimento total do trajeto (mm)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.size < 2:
        return 0.0
    return float(np.hypot(np.diff(x), np.diff(y)).sum())


def speed_series(x, y, sample_rate_hz):
    """Velocidade instantânea do CoP (mm/s), uma amostra a menos que a trajetória."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.size < 2:
        return np.zeros(0)
    return np.hypot(np.diff(x), np.diff(y)) * sample_rate_hz


def compute_global_metrics(x, y, sample_rate_hz):
    """
    Métricas globais para preencher StabilometryResult ao receber um exame:
    path_length_mm, area_mm2, extension_area_ratio, avg_velocity_mm_s.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    length = path_length(x, y)
    area = bbox_ellipse_area(x, y)
    duration = (x.size - 1) / sample_rate_hz if x.size > 1 and sample_rate_hz else 0.0
    return {
        'path_length_mm': round(length, 2),
        'area_mm2': round(area, 2),
        'extension_area_ratio': round(length / area, 2) if area else 0.0,
        'avg_velocity_mm_s': round(length / duration, 2) if duration else 0.0,
    }
