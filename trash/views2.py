import json
import random
import numpy as np
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Avg, Max, Count
from django.utils import timezone

from ..core.models import (
    Patient, Exam, FootAnalysis, PressureSnapshot,
    StabilometryResult, PressureDistribution,
)
from ..core.forms import PatientForm, ExamForm
from django.conf import settings


def dashboard(request):
    """Dashboard principal com mapa de calor em tempo real."""
    recent_exams = Exam.objects.select_related('patient').all()[:5]
    total_patients = Patient.objects.count()
    total_exams = Exam.objects.count()

    context = {
        'recent_exams': recent_exams,
        'total_patients': total_patients,
        'total_exams': total_exams,
        'grid_rows': settings.SENSOR_GRID_ROWS,
        'grid_cols': settings.SENSOR_GRID_COLS,
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
        'matrix': snapshot.pressure_matrix,
        'captured_at': snapshot.captured_at.isoformat(),
    })


@require_GET
def api_simulate_frame(request):
    """
    Gera um frame simulado (como se viesse do ESP32).
    Útil para testar o dashboard sem hardware.
    """
    rows = settings.SENSOR_GRID_ROWS
    cols = settings.SENSOR_GRID_COLS

    # Gera uma matriz simulando uma pisada (gaussianas no calcanhar e metatarso)
    matrix = _generate_simulated_footstep(rows, cols)

    return JsonResponse({
        'rows': rows,
        'cols': cols,
        'matrix': matrix.tolist(),
        'timestamp': timezone.now().isoformat(),
    })


def _generate_simulated_footstep(rows, cols):
    """Gera uma matriz simulando a distribuição de pressão de uma pisada."""
    matrix = np.zeros((rows, cols))
    y, x = np.ogrid[0:rows, 0:cols]

    # Calcanhar (parte inferior central)
    heel_cx, heel_cy = cols // 2, int(rows * 0.85)
    heel = 0.6 * np.exp(-((x - heel_cx) ** 2 + (y - heel_cy) ** 2) / 30)

    # Metatarso medial (hálux)
    meta_med_cx, meta_med_cy = int(cols * 0.35), int(rows * 0.2)
    meta_med = 0.55 * np.exp(-((x - meta_med_cx) ** 2 + (y - meta_med_cy) ** 2) / 15)

    # Metatarso lateral
    meta_lat_cx, meta_lat_cy = int(cols * 0.65), int(rows * 0.22)
    meta_lat = 0.4 * np.exp(-((x - meta_lat_cx) ** 2 + (y - meta_lat_cy) ** 2) / 18)

    # Arco (pressão baixa)
    arch_cx, arch_cy = int(cols * 0.55), int(rows * 0.5)
    arch = 0.15 * np.exp(-((x - arch_cx) ** 2 + (y - arch_cy) ** 2) / 40)

    matrix = heel + meta_med + meta_lat + arch

    # Adiciona ruído para simular sensores reais
    noise = np.random.normal(0, 0.02, matrix.shape)
    matrix = np.clip(matrix + noise, 0, 1.0)

    return matrix