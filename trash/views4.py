import json
import random
import numpy as np
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Avg, Max, Count
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Patient, Exam, FootAnalysis, PressureSnapshot,
    StabilometryResult, PressureDistribution,
)
from .forms import PatientForm, ExamForm
from django.conf import settings

# Pressão (kgf/cm²) que corresponde ao vermelho máximo do mapa de calor.
# Deve bater com a legenda do dashboard (0 … 8+). Pode ser sobrescrito no settings.py.
PRESSURE_MAX_KGF = getattr(settings, 'SENSOR_PRESSURE_MAX_KGF', 8.0)

# Quantos frames dura um ciclo de passo na simulação (calcanhar -> antepé).
SIMULATION_CYCLE_FRAMES = 30


def service_worker(request):
    return render(request, 'sw.js', content_type='application/javascript')

def dashboard(request):
    """
    Dashboard de análise de pisada.

    Mostra o exame selecionado em ?exam=<id> (ou o mais recente) com dados reais
    do paciente, análise por pé, distribuição de pressão e estabilometria.
    O mapa de calor é desenhado no front-end (snapshot salvo ou simulação).
    """
    exams_qs = Exam.objects.select_related('patient', 'doctor')

    exam = None
    exam_id = request.GET.get('exam', '')
    if exam_id.isdigit():
        exam = exams_qs.filter(pk=int(exam_id)).first()
    if exam is None:
        exam = exams_qs.first()  # Meta.ordering = ['-exam_date'] -> o mais recente

    foot_left = foot_right = None
    distributions = []
    stabilometry = None
    peak_pressure = None

    if exam:
        analyses = {fa.side: fa for fa in exam.foot_analyses.all()}
        foot_left = analyses.get('L')
        foot_right = analyses.get('R')
        distributions = exam.pressure_distributions.all()
        stabilometry = getattr(exam, 'stabilometry', None)

        peaks = [fa.max_pressure_kgf_cm2 for fa in analyses.values()]
        peak_pressure = max(peaks) if peaks else None

    context = {
        'exam': exam,
        'patient': exam.patient if exam else None,
        'foot_left': foot_left,
        'foot_right': foot_right,
        'distributions': distributions,
        'stabilometry': stabilometry,
        'peak_pressure': peak_pressure,
        'selectable_exams': exams_qs[:30],
        'recent_exams': exams_qs[:5],
        'total_patients': Patient.objects.count(),
        'total_exams': Exam.objects.count(),
        'grid_rows': settings.SENSOR_GRID_ROWS,
        'grid_cols': settings.SENSOR_GRID_COLS,
        'pressure_max': PRESSURE_MAX_KGF,
    }
    return render(request, 'core/dashboard.html', context)


def patients_list(request):
    """Lista de pacientes."""
    patients = Patient.objects.annotate(
        exam_count=Count('exams')
    ).order_by('name')
    return render(request, 'core/patients_list.html', {'patients': patients})


def patient_create(request):
    """Criar novo paciente."""
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save()
            return redirect('patient_detail', pk=patient.pk)
    else:
        form = PatientForm()
    return render(request, 'core/patient_form.html', {
        'form': form, 'title': 'Novo Paciente'
    })


def patient_edit(request, pk):
    """Editar paciente."""
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            return redirect('patient_detail', pk=patient.pk)
    else:
        form = PatientForm(instance=patient)
    return render(request, 'core/patient_form.html', {
        'form': form, 'title': f'Editar {patient.name}'
    })


def patient_detail(request, pk):
    """Detalhes do paciente com histórico de exames."""
    patient = get_object_or_404(Patient, pk=pk)
    exams = patient.exams.select_related('doctor').all()
    context = {'patient': patient, 'exams': exams}
    return render(request, 'core/patient_detail.html', context)


def history(request):
    """Histórico geral de exames."""
    exams = Exam.objects.select_related('patient', 'doctor').all()

    exam_type = request.GET.get('type')
    if exam_type:
        exams = exams.filter(exam_type=exam_type)

    patient_id = request.GET.get('patient')
    if patient_id:
        exams = exams.filter(patient_id=patient_id)

    context = {
        'exams': exams,
        'patients': Patient.objects.all(),
        'exam_types': Exam.EXAM_TYPES,
    }
    return render(request, 'core/history.html', context)


def exam_detail(request, pk):
    """Detalhes do exame com visualização do mapa de calor."""
    exam = get_object_or_404(
        Exam.objects.select_related('patient', 'doctor'), pk=pk
    )
    foot_analyses = exam.foot_analyses.all()
    distributions = exam.pressure_distributions.all()
    stabilometry = getattr(exam, 'stabilometry', None)

    # Último snapshot de cada pé para exibir o mapa
    left_snapshot = exam.pressure_snapshots.filter(side='L').order_by('-frame_index').first()
    right_snapshot = exam.pressure_snapshots.filter(side='R').order_by('-frame_index').first()

    context = {
        'exam': exam,
        'foot_analyses': foot_analyses,
        'distributions': distributions,
        'stabilometry': stabilometry,
        'left_snapshot': left_snapshot,
        'right_snapshot': right_snapshot,
        'grid_rows': settings.SENSOR_GRID_ROWS,
        'grid_cols': settings.SENSOR_GRID_COLS,
    }
    return render(request, 'core/exam_detail.html', context)


def exam_report_pdf(request, pk):
    """
    Relatório PDF do exame (mapa de calor, distribuição, estabilometria e 3D).
    Abre no navegador; use ?download=1 para forçar o download.
    """
    exam = get_object_or_404(
        Exam.objects.select_related('patient', 'doctor'), pk=pk
    )
    try:
        from .reports import render_exam_pdf  # import tardio: matplotlib/WeasyPrint são pesados
        pdf = render_exam_pdf(exam)
    except (ImportError, OSError) as exc:
        return HttpResponse(
            'Não foi possível gerar o PDF: instale as dependências (pip install weasyprint matplotlib) '
            f'e as bibliotecas do sistema do WeasyPrint. Detalhe: {exc}',
            status=503, content_type='text/plain; charset=utf-8',
        )

    filename = f"baropodometria-{slugify(exam.patient.name)}-{exam.exam_date:%Y%m%d}.pdf"
    disposition = 'attachment' if request.GET.get('download') else 'inline'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


# ============ APIs para o frontend ============

@require_GET
def api_latest_snapshot(request, exam_id):
    """Retorna o último snapshot de pressão de um exame (para o mapa de calor)."""
    exam = get_object_or_404(Exam, pk=exam_id)
    side = request.GET.get('side', 'L')

    snapshot = exam.pressure_snapshots.filter(side=side).order_by('-frame_index').first()
    if not snapshot:
        return JsonResponse({'error': 'Sem dados'}, status=404)

    return JsonResponse({
        'exam_id': exam.id,
        'side': snapshot.side,
        'frame': snapshot.frame_index,
        'rows': settings.SENSOR_GRID_ROWS,
        'cols': settings.SENSOR_GRID_COLS,
        'max_value': PRESSURE_MAX_KGF,  # escala do heatmap (kgf/cm² = cor máxima)
        'matrix': snapshot.pressure_matrix,
        'captured_at': snapshot.captured_at.isoformat(),
    })


@require_GET
def api_simulate_frame(request):
    """
    Gera um frame simulado (como se viesse do ESP32).
    Útil para testar o dashboard sem hardware.

    Parâmetro opcional ?frame=N faz o "passo" avançar (calcanhar -> antepé).
    Os valores saem em kgf/cm², na mesma escala dos snapshots reais.
    """
    rows = settings.SENSOR_GRID_ROWS
    cols = settings.SENSOR_GRID_COLS

    try:
        frame = max(0, int(request.GET.get('frame', 0)))
    except ValueError:
        frame = 0

    matrix = _generate_simulated_footstep(rows, cols, frame) * PRESSURE_MAX_KGF

    return JsonResponse({
        'rows': rows,
        'cols': cols,
        'frame': frame,
        'max_value': PRESSURE_MAX_KGF,
        'matrix': np.round(matrix, 3).tolist(),
        'timestamp': timezone.now().isoformat(),
    })


def _generate_simulated_footstep(rows, cols, frame=0):
    """
    Gera uma matriz (0..1) simulando a pressão plantar durante o passo.

    As posições seguem o mapa `mapa_planta_pe.png` (lado medial/hálux à direita,
    calcanhar embaixo). Os tamanhos das manchas são frações da grade, então
    funcionam com qualquer SENSOR_GRID_ROWS x SENSOR_GRID_COLS.
    """
    y, x = np.ogrid[0:rows, 0:cols]

    def blob(cx, cy, amp, sx, sy):
        """Gaussiana centrada em (cx, cy) [fração da grade], desvio sx/sy [fração]."""
        dx = (x - cols * cx) / (cols * sx)
        dy = (y - rows * cy) / (rows * sy)
        return amp * np.exp(-0.5 * (dx ** 2 + dy ** 2))

    # Ciclo do passo: começa no calcanhar e rola para o antepé.
    phase = 2 * np.pi * (frame % SIMULATION_CYCLE_FRAMES) / SIMULATION_CYCLE_FRAMES
    heel_gain = 0.3 + (0.5 + 0.5 * np.cos(phase))   # 0.3 .. 1.3
    fore_gain = 0.3 + (0.5 - 0.5 * np.cos(phase))   # 0.3 .. 1.3

    heel = blob(0.50, 0.85, 0.60, 0.13, 0.08) * heel_gain
    hallux = blob(0.62, 0.13, 0.45, 0.08, 0.04) * fore_gain
    toes = blob(0.38, 0.16, 0.20, 0.15, 0.035) * fore_gain
    meta_med = blob(0.60, 0.31, 0.55, 0.09, 0.05) * fore_gain
    meta_lat = blob(0.36, 0.33, 0.40, 0.09, 0.05) * fore_gain
    arch = blob(0.42, 0.58, 0.15, 0.06, 0.12)       # arco: pressão baixa e constante

    matrix = heel + hallux + toes + meta_med + meta_lat + arch

    # Ruído para simular sensores reais
    noise = np.random.normal(0, 0.02, matrix.shape)
    return np.clip(matrix + noise, 0, 1.0)
