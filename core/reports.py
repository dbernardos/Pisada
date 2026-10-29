"""
Relatório PDF do exame de baropodometria.

Fluxo:
    collect_exam_data(exam)  -> lê o banco e devolve um dict simples (sem ORM)
    build_context(data)      -> calcula métricas, gera os gráficos (matplotlib) e o contexto do template
    render_exam_pdf(exam)    -> renderiza core/report/exam_report.html e converte para PDF (WeasyPrint)

Configurações opcionais (settings.py):
    SENSOR_PITCH_MM = 10.0            distância entre sensores, em mm (para cm², cm e mm dos gráficos)
    REPORT_FEET_GAP_CELLS = None      espaço entre os pés no mapa (None = metade da largura de um pé)
    REPORT_MIRROR_RIGHT_FOOT = True   espelha o pé direito (use True se as matrizes dos dois pés vierem
                                      na mesma orientação, como no simulador; False se a palmilha
                                      direita já entrega a matriz espelhada)
    REPORT_MAX_FRAMES = 300           máximo de frames lidos por pé
"""
import base64
import io
import math

import numpy as np
import matplotlib

matplotlib.use('Agg')  # sem interface gráfica (servidor)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Ellipse, Rectangle  # noqa: E402

from django.conf import settings  # noqa: E402
from django.template.loader import render_to_string  # noqa: E402
from django.utils import timezone  # noqa: E402

from .stabilometry import bbox_ellipse_area, extent, speed_series  # noqa: E402

# Mesma escala de cores do dashboard (azul -> ciano -> verde -> amarelo -> vermelho).
PRESSURE_CMAP = LinearSegmentedColormap.from_list(
    'pressure', ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000']
)
BRAND = '#0b6fa4'
BRAND_LIGHT = '#9fc5de'
PAGE_WIDTH_IN = 7.1  # largura útil do A4 com margens de 15 mm


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def _cfg(name, default):
    return getattr(settings, name, default)


def fmt(value, digits=2, suffix=''):
    """Número no padrão brasileiro (1.234,56). None vira '—'."""
    if value is None:
        return '—'
    text = f'{value:,.{digits}f}'.replace(',', '#').replace('.', ',').replace('#', '.')
    return f'{text}{suffix}'


def _dash(value, suffix=''):
    return '—' if value in (None, '') else f'{value}{suffix}'


def _fig_to_data_uri(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, facecolor='white')
    plt.close(fig)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _file_to_data_uri(path):
    import mimetypes
    mime = mimetypes.guess_type(path)[0] or 'image/png'
    with open(path, 'rb') as fh:
        return f'data:{mime};base64,' + base64.b64encode(fh.read()).decode('ascii')


def _static_data_uri(relative_path):
    """Lê um arquivo estático (ex.: logo) e devolve data URI; None se não existir."""
    try:
        from django.contrib.staticfiles import finders
        found = finders.find(relative_path)
        if not found and getattr(settings, 'STATIC_ROOT', None):
            import os
            candidate = os.path.join(settings.STATIC_ROOT, relative_path)
            found = candidate if os.path.exists(candidate) else None
        if isinstance(found, (list, tuple)):
            found = found[0] if found else None
        return _file_to_data_uri(found) if found else None
    except Exception:
        return None


def _upsample(matrix, factor):
    """Interpolação bilinear da grade de sensores (só numpy, sem scipy)."""
    rows, cols = matrix.shape
    ys = np.linspace(0, rows - 1, (rows - 1) * factor + 1)
    xs = np.linspace(0, cols - 1, (cols - 1) * factor + 1)
    tmp = np.array([np.interp(xs, np.arange(cols), row) for row in matrix])
    return np.array([np.interp(ys, np.arange(rows), tmp[:, j]) for j in range(tmp.shape[1])]).T


def _cop(matrix, x_offset=0.0):
    """Centro de pressão (x, y) em coordenadas de célula; None se a matriz for vazia."""
    total = matrix.sum()
    if total <= 0:
        return None
    ys, xs = np.indices(matrix.shape)
    return (xs * matrix).sum() / total + x_offset, (ys * matrix).sum() / total


# ----------------------------------------------------------------------------
# 1) Coleta (única parte que toca o banco)
# ----------------------------------------------------------------------------
def _load_matrix(exam, side, mode):
    """Matriz única do pé: média (estática) ou máximo por sensor (dinâmica) dos snapshots."""
    limit = _cfg('REPORT_MAX_FRAMES', 300)
    raw = list(
        exam.pressure_snapshots.filter(side=side)
        .order_by('-frame_index')
        .values_list('pressure_matrix', flat=True)[:limit]
    )
    mats = []
    for m in raw:
        arr = np.asarray(m, dtype=float)
        if arr.ndim == 2 and (not mats or arr.shape == mats[0].shape):
            mats.append(arr)
    if not mats:
        return None, 0
    stack = np.stack(mats)
    return (stack.max(axis=0) if mode == 'peak' else stack.mean(axis=0)), len(mats)


def collect_exam_data(exam):
    patient, doctor = exam.patient, exam.doctor
    mode = 'peak' if exam.exam_type == 'DYNAMIC' else 'mean'

    matrices, frames = {}, {}
    for side in ('L', 'R'):
        matrices[side], frames[side] = _load_matrix(exam, side, mode)

    analyses = {}
    for fa in exam.foot_analyses.all():
        analyses[fa.side] = {
            'surface': fa.surface_cm2,
            'pmax': fa.max_pressure_kgf_cm2,
            'pavg': fa.avg_pressure_kgf_cm2,
            'load': fa.load_percentage,
        }

    stab = getattr(exam, 'stabilometry', None)
    stab_data = None
    if stab:
        stab_data = {
            'path_length_mm': stab.path_length_mm,
            'area_mm2': stab.area_mm2,
            'extension_area_ratio': stab.extension_area_ratio,
            'avg_velocity_mm_s': stab.avg_velocity_mm_s,
            'sway': (stab.sway_left, stab.sway_right, stab.sway_anterior, stab.sway_posterior),
            'sample_rate_hz': stab.sample_rate_hz or 10.0,
            'cop_body': stab.cop_body,
            'cop_left': stab.cop_left,
            'cop_right': stab.cop_right,
        }

    doctor_data = None
    if doctor:
        signature_path = None
        if getattr(doctor, 'signature', None):
            try:
                signature_path = doctor.signature.path
            except (ValueError, NotImplementedError):
                signature_path = None
        doctor_data = {
            'name': doctor.name,
            'crefito': doctor.crefito,
            'title': doctor.report_title,
            'subtitle': doctor.report_subtitle or doctor.specialty,
            'signature_path': signature_path,
        }

    return {
        'exam': {
            'type': exam.exam_type,
            'date': timezone.localtime(exam.exam_date),
            'footwear': exam.footwear,
        },
        'patient': {
            'name': patient.name,
            'birth_date': patient.birth_date,
            'age': patient.age,
            'weight_kg': patient.weight_kg,
            'height_m': patient.height_m,
        },
        'doctor': doctor_data,
        'matrices': matrices,
        'frames': frames,
        'analyses': analyses,
        'stab': stab_data,
    }


# ----------------------------------------------------------------------------
# 2) Gráficos
# ----------------------------------------------------------------------------
def _static_figure(composite, cols, gap, vmax, thr, cops, quads, pitch_mm):
    """Mapa de calor dos dois pés com eixos do centro de pressão e % por quadrante."""
    height, width = composite.shape
    fig, ax = plt.subplots(figsize=(PAGE_WIDTH_IN, 5.4))

    masked = np.ma.masked_less(_upsample(composite, 6), thr)
    image = ax.imshow(
        masked, cmap=PRESSURE_CMAP, vmin=0, vmax=vmax, interpolation='bilinear',
        extent=(-0.5, width - 0.5, height - 0.5, -0.5), aspect='equal',
    )

    center_x = cols + gap / 2 - 0.5
    body = cops.get('body')
    ax.plot([center_x, center_x], [-0.5, height - 0.5], color='#222', lw=0.8)
    if body:
        ax.plot([-0.5, width - 0.5], [body[1], body[1]], color='#222', lw=0.8)

    for key in ('left', 'right'):
        point = cops.get(key)
        if point and body:
            ax.plot([point[0], body[0]], [point[1], body[1]], color='#222', lw=0.8)
            dist_cm = math.hypot(point[0] - body[0], point[1] - body[1]) * pitch_mm / 10
            ax.text((point[0] + body[0]) / 2, body[1] - 0.8, f'{fmt(dist_cm)} cm',
                    ha='center', va='bottom', fontsize=7, zorder=5,
                    bbox=dict(fc='white', ec='none', alpha=0.85, pad=1.0))
        if point:
            ax.plot(*point, marker='o', color='#222', ms=6)
    if body:
        ax.plot(*body, marker='o', color='#222', ms=8, mfc='white', mew=1.5)

    corners = [('LA', 0.02, 0.98, 'left', 'top'), ('RA', 0.98, 0.98, 'right', 'top'),
               ('LP', 0.02, 0.02, 'left', 'bottom'), ('RP', 0.98, 0.02, 'right', 'bottom')]
    for key, px, py, ha, va in corners:
        ax.text(px, py, fmt(quads[key], 2, ' %'), transform=ax.transAxes,
                ha=ha, va=va, fontsize=8, color='#334155')

    # Faixa extra em cima e embaixo para os percentuais não ficarem sobre os pés.
    margin = 3
    ax.set_xlim(-0.5, width - 0.5)
    ax.set_ylim(height - 0.5 + margin, -0.5 - margin)
    ax.axis('off')

    cbar = fig.colorbar(image, ax=ax, orientation='horizontal', fraction=0.035, pad=0.01, shrink=0.45)
    cbar.set_label('kgf/cm²', fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    return _fig_to_data_uri(fig)


def _surface_figure(composite, vmax, thr):
    """Superfície 3D da pressão dos dois pés."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registra a projeção 3d)

    up = _upsample(composite, 3)
    z = np.where(up < thr, np.nan, up)
    rows, cols = up.shape
    y_idx, x_idx = np.mgrid[0:rows, 0:cols]
    y = (rows - 1) - y_idx  # dedos (linha 0) ficam no fundo da cena

    fig = plt.figure(figsize=(PAGE_WIDTH_IN, 5.0))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(x_idx, y, z, cmap=PRESSURE_CMAP, vmin=0, vmax=vmax,
                    rstride=1, cstride=1, linewidth=0, antialiased=False)
    ax.set_zlim(0, vmax)
    ax.set_box_aspect((cols, rows, max(cols, rows) * 0.35))
    ax.view_init(elev=52, azim=-90)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return _fig_to_data_uri(fig)


def _cop_figure(x, y, color, title, size, area_override=None):
    """Trajetória do CoP com retângulo envolvente, elipse inscrita e dimensões em mm."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    width, height = extent(x), extent(y)
    area = area_override if area_override else bbox_ellipse_area(x, y)
    x_min, x_max, y_min, y_max = x.min(), x.max(), y.min(), y.max()

    fig, ax = plt.subplots(figsize=size)
    ax.plot(x, y, color='#444', lw=0.5, ls='--', zorder=1)
    ax.scatter(x, y, s=5, color=color, zorder=2)
    ax.add_patch(Rectangle((x_min, y_min), width, height, fill=False, ec='#555', lw=0.8, ls='--'))
    ax.add_patch(Ellipse(((x_min + x_max) / 2, (y_min + y_max) / 2), width, height,
                         fill=False, ec=color, lw=1.6))

    pad = max(width, height, 1.0) * 0.12
    ax.text((x_min + x_max) / 2, y_min - pad * 0.5, f'{fmt(width)} mm', ha='center', va='top', fontsize=8)
    ax.text(x_min - pad * 0.5, (y_min + y_max) / 2, f'{fmt(height)} mm', ha='right', va='center',
            rotation=90, fontsize=8)
    ax.set_xlim(x_min - pad * 2.2, x_max + pad)
    ax.set_ylim(y_min - pad * 2.2, y_max + pad)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f'{title} ({fmt(area)} mm²)', fontsize=10)
    return _fig_to_data_uri(fig), area


def _series_figure(body, fs):
    """Oscilação latero-lateral, antero-posterior e velocidade do CoP ao longo do tempo."""
    x, y = np.asarray(body['x'], dtype=float), np.asarray(body['y'], dtype=float)
    t = np.arange(x.size) / fs
    speed = speed_series(x, y, fs)

    fig, axes = plt.subplots(3, 1, figsize=(PAGE_WIDTH_IN, 5.9))
    panels = [
        (axes[0], t, x - x[0], '#00a6e0', 'Oscilação latero-lateral', 'Amplitude (mm)', ('Direita', 'Esquerda')),
        (axes[1], t, y - y[0], '#00a6e0', 'Oscilação antero-posterior', 'Amplitude (mm)', ('Anterior', 'Posterior')),
        (axes[2], t[1:], speed, '#e11d1d', 'Velocidade do centro de pressão', 'mm/s', None),
    ]
    for ax, tt, values, color, title, ylabel, ends in panels:
        ax.plot(tt, values, color=color, lw=1.0)
        ax.set_title(title, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_xlabel('Tempo (s)', fontsize=8)
        ax.grid(True, color='#e2e8f0', lw=0.6)
        ax.set_facecolor('#f8fafc')
        ax.tick_params(labelsize=7)
        for spine in ('top', 'right'):
            ax.spines[spine].set_visible(False)
        if ends:
            ax.text(0.005, 0.97, ends[0] + ' ▲', transform=ax.transAxes, fontsize=7, va='top', color='#475569')
            ax.text(0.005, 0.03, ends[1] + ' ▼', transform=ax.transAxes, fontsize=7, va='bottom', color='#475569')
    fig.tight_layout(h_pad=1.6)
    return _fig_to_data_uri(fig)


def _gauge_svg(kind, a_pct, b_pct, a_label, b_label):
    """
    Indicador em anel dividido em duas metades; o lado com mais carga fica mais grosso.
    kind='ap'  -> a = parte de cima, b = parte de baixo
    kind='lat' -> a = lado esquerdo, b = lado direito
    """
    cx, cy, r = 180, 130, 62

    def width(pct):
        return min(40.0, 6 + 60 * pct / 100)

    def color(pct, other):
        return BRAND if pct >= other else BRAND_LIGHT

    if kind == 'ap':
        arc_a = f'M {cx - r} {cy} A {r} {r} 0 0 1 {cx + r} {cy}'
        arc_b = f'M {cx + r} {cy} A {r} {r} 0 0 1 {cx - r} {cy}'
        divider = f'<line x1="{cx - r - 40}" y1="{cy}" x2="{cx + r + 40}" y2="{cy}" stroke="#64748b" stroke-width="2"/>'
        texts = (
            f'<text x="{cx}" y="14" text-anchor="middle" font-size="12" fill="#475569">{a_label}</text>'
            f'<text x="{cx}" y="36" text-anchor="middle" font-size="19" font-weight="700" fill="#0f172a">{fmt(a_pct)} %</text>'
            f'<text x="{cx}" y="238" text-anchor="middle" font-size="19" font-weight="700" fill="#0f172a">{fmt(b_pct)} %</text>'
            f'<text x="{cx}" y="254" text-anchor="middle" font-size="12" fill="#475569">{b_label}</text>'
        )
    else:
        arc_a = f'M {cx} {cy + r} A {r} {r} 0 0 1 {cx} {cy - r}'   # metade esquerda
        arc_b = f'M {cx} {cy - r} A {r} {r} 0 0 1 {cx} {cy + r}'   # metade direita
        divider = f'<line x1="{cx}" y1="{cy - r - 40}" x2="{cx}" y2="{cy + r + 40}" stroke="#64748b" stroke-width="2"/>'
        texts = (
            f'<text x="6" y="124" font-size="12" fill="#475569">{a_label}</text>'
            f'<text x="6" y="146" font-size="19" font-weight="700" fill="#0f172a">{fmt(a_pct)} %</text>'
            f'<text x="354" y="124" text-anchor="end" font-size="12" fill="#475569">{b_label}</text>'
            f'<text x="354" y="146" text-anchor="end" font-size="19" font-weight="700" fill="#0f172a">{fmt(b_pct)} %</text>'
        )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 262" width="100%" '
        'font-family="DejaVu Sans, Arial, sans-serif">'
        f'<path d="{arc_a}" fill="none" stroke="{color(a_pct, b_pct)}" stroke-width="{width(a_pct):.1f}"/>'
        f'<path d="{arc_b}" fill="none" stroke="{color(b_pct, a_pct)}" stroke-width="{width(b_pct):.1f}"/>'
        f'{divider}{texts}</svg>'
    )


# ----------------------------------------------------------------------------
# 3) Contexto do template
# ----------------------------------------------------------------------------
def _pct(part, total):
    return part / total * 100 if total > 0 else 0.0


def _build_pressure_section(data, ctx):
    """Páginas de pressão: análise estática/dinâmica, distribuição e 3D."""
    left, right = data['matrices']['L'], data['matrices']['R']
    reference = left if left is not None else right
    if reference is None:
        return False

    shape = reference.shape
    left = left if left is not None else np.zeros(shape)
    right = right if right is not None and right.shape == shape else np.zeros(shape)
    rows, cols = shape

    pitch_mm = float(_cfg('SENSOR_PITCH_MM', 10.0))
    gap = _cfg('REPORT_FEET_GAP_CELLS', None)
    gap = max(2, cols // 2) if gap is None else int(gap)
    right_display = right[:, ::-1] if _cfg('REPORT_MIRROR_RIGHT_FOOT', True) else right

    composite = np.hstack([left, np.zeros((rows, gap)), right_display])
    vmax = float(composite.max()) or 1.0
    thr = 0.03 * vmax

    # Quadrantes (% da pressão total): anterior = metade de cima da grade de cada pé.
    half = rows // 2
    parts = {'LA': left[:half].sum(), 'LP': left[half:].sum(),
             'RA': right[:half].sum(), 'RP': right[half:].sum()}
    total = sum(parts.values())
    quads = {k: _pct(v, total) for k, v in parts.items()}
    left_total, right_total = parts['LA'] + parts['LP'], parts['RA'] + parts['RP']

    cops = {
        'left': _cop(left),
        'right': _cop(right_display, cols + gap),
        'body': _cop(composite),
    }
    ctx['static_image'] = _static_figure(composite, cols, gap, vmax, thr, cops, quads, pitch_mm)
    ctx['surface_image'] = _surface_figure(composite, vmax, thr)

    # Tabela por pé: usa FootAnalysis; se não existir, calcula a partir da matriz.
    feet = []
    for side, label, matrix in (('L', 'Pé Esquerdo', left), ('R', 'Pé Direito', right)):
        analysis = data['analyses'].get(side)
        active = matrix[matrix >= thr]
        if analysis:
            surface, pmax, pavg, load = (analysis['surface'], analysis['pmax'],
                                         analysis['pavg'], analysis['load'])
        else:
            surface = active.size * (pitch_mm / 10) ** 2 if active.size else None
            pmax = float(matrix.max()) if matrix.size else None
            pavg = float(active.mean()) if active.size else None
            load = _pct(matrix.sum(), left_total + right_total)
        feet.append({
            'label': label,
            'surface': fmt(surface, 2, ' cm²'),
            'load': fmt(load, 2, ' %'),
            'pmax': fmt(pmax, 2, ' kgf/cm²'),
            'pavg': fmt(pavg, 2, ' kgf/cm²'),
        })
    ctx['feet'] = feet

    ctx['gauges'] = {
        'ap': _gauge_svg('ap', quads['LA'] + quads['RA'], quads['LP'] + quads['RP'], 'Anterior', 'Posterior'),
        'lat': _gauge_svg('lat', _pct(left_total, total), _pct(right_total, total), 'Esquerdo', 'Direito'),
        'left': _gauge_svg('ap', _pct(parts['LA'], left_total), _pct(parts['LP'], left_total),
                           'Anterior', 'Posterior'),
        'right': _gauge_svg('ap', _pct(parts['RA'], right_total), _pct(parts['RP'], right_total),
                            'Anterior', 'Posterior'),
    }

    frames = max(data['frames'].values() or [0])
    if data['exam']['type'] == 'DYNAMIC':
        ctx['static_note'] = f'Maior pressão registrada em cada sensor ao longo de {frames} frames.'
    else:
        ctx['static_note'] = f'Média de {frames} frame{"s" if frames != 1 else ""} capturado{"s" if frames != 1 else ""}.'
    return True


def _build_stabilometry_section(data, ctx):
    stab = data['stab']
    if not stab:
        return [], False

    ctx['stab'] = {
        'path_length': fmt(stab['path_length_mm'], 2, ' mm'),
        'area': fmt(stab['area_mm2'], 2, ' mm²'),
        'ratio': fmt(stab['extension_area_ratio'], 2, ' 1/mm'),
        'velocity': fmt(stab['avg_velocity_mm_s'], 2, ' mm/s'),
        'sway': None,
    }
    if any(stab['sway']):
        left, right, ant, post = stab['sway']
        ctx['stab']['sway'] = (f'Oscilação — esquerda {fmt(left, 1)} % · direita {fmt(right, 1)} % · '
                               f'anterior {fmt(ant, 1)} % · posterior {fmt(post, 1)} %')

    def usable(trace):
        return bool(trace) and len(trace.get('x', [])) > 1 and len(trace.get('x', [])) == len(trace.get('y', []))

    fs = float(stab['sample_rate_hz'])
    ctx['cop_body_image'] = ctx['cop_left_image'] = ctx['cop_right_image'] = None
    if usable(stab['cop_body']):
        ctx['cop_body_image'], _ = _cop_figure(stab['cop_body']['x'], stab['cop_body']['y'],
                                               '#00a6e0', 'Corpo', (3.9, 3.4),
                                               area_override=stab['area_mm2'])
    if usable(stab['cop_left']):
        ctx['cop_left_image'], _ = _cop_figure(stab['cop_left']['x'], stab['cop_left']['y'],
                                               '#dc2626', 'Pé Esquerdo', (3.4, 4.2))
    if usable(stab['cop_right']):
        ctx['cop_right_image'], _ = _cop_figure(stab['cop_right']['x'], stab['cop_right']['y'],
                                                '#1d4ed8', 'Pé Direito', (3.4, 4.2))

    pages = ['stab_global']
    if usable(stab['cop_body']):
        ctx['series_image'] = _series_figure(stab['cop_body'], fs)
        pages.append('stab_series')
    return pages, True


def build_context(data):
    exam, patient, doctor = data['exam'], data['patient'], data['doctor']

    title = (doctor and doctor['title']) or (f"Dr(a). {doctor['name']}" if doctor else 'Relatório de Baropodometria')
    subtitle = (doctor and doctor['subtitle']) or ''

    birth = patient['birth_date']
    ctx = {
        'report_title': title,
        'report_subtitle_lines': [ln.strip() for ln in subtitle.splitlines() if ln.strip()],
        'patient_name': patient['name'],
        'birth_text': f"{birth:%d/%m/%Y} ({patient['age']} anos)",
        'exam_date_text': f"{exam['date']:%d/%m/%Y - %H:%M:%S}",
        'footwear_text': _dash(exam['footwear']),
        'weight_text': _dash(patient['weight_kg'] or None, ' kg'),
        'height_text': _dash(patient['height_m'] or None, ' m'),
        'responsible': doctor['name'].upper() if doctor else '—',
        'report_date': timezone.localdate().strftime('%d/%m/%Y'),
        'logo': _static_data_uri('core/images/logo.png'),
        'analysis_title': {'STATIC': 'Análise Estática', 'DYNAMIC': 'Análise Dinâmica'}.get(
            exam['type'], 'Análise de Pressão'),
        'signature': _file_to_data_uri(doctor['signature_path']) if doctor and doctor['signature_path'] else None,
        'signature_name': (f"{doctor['name'].upper()} CREFITO {doctor['crefito']}" if doctor else ''),
    }

    pages = []
    has_pressure = _build_pressure_section(data, ctx)
    if has_pressure:
        pages += ['static', 'distribution']
    stab_pages, _ = _build_stabilometry_section(data, ctx)
    pages += stab_pages
    if has_pressure:
        pages.append('surface')

    ctx['pages'] = pages
    ctx['last_page'] = pages[-1] if pages else None
    return ctx


# ----------------------------------------------------------------------------
# 4) PDF
# ----------------------------------------------------------------------------
def render_exam_pdf(exam):
    """Gera o PDF do exame e devolve os bytes. Levanta ImportError/OSError se o WeasyPrint faltar."""
    from weasyprint import HTML  # import tardio: só quem gera PDF precisa dele

    context = build_context(collect_exam_data(exam))
    html = render_to_string('core/report/exam_report.html', context)
    return HTML(string=html).write_pdf()
