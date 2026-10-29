import random
import numpy as np
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import (
    Patient, Doctor, Exam, FootAnalysis,
    PressureSnapshot, StabilometryResult,
    PressureDistribution, SensorCalibration,
)
from django.conf import settings


class Command(BaseCommand):
    help = 'Popula o banco com dados de exemplo baseados no relatório PDF'

    def handle(self, *args, **options):
        self.stdout.write('Populando banco de dados...')

        # 1) Profissional (extraído do PDF)
        doctor, _ = Doctor.objects.get_or_create(
            crefito='CREFITO 321982-F',
            defaults={
                'name': 'Pedro Felipe Santos',
                'specialty': 'Fisioterapia especializada - Traumato ortopédica / Osteopatia / Baropodometria',
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  Profissional: {doctor.name}'))

        # 2) Pacientes (5 registros, incluindo Marcos do PDF)
        patients_data = [
            {
                'name': 'Marcos',
                'birth_date': '1985-06-11',
                'weight_kg': 78.0,
                'height_m': 1.75,
                'gender': 'M',
                'phone': '(11) 98765-4321',
                'email': 'marcos@email.com',
                'notes': 'Paciente referência do relatório de baropodometria.',
            },
            {
                'name': 'Ana Carolina Silva',
                'birth_date': '1992-03-25',
                'weight_kg': 62.0,
                'height_m': 1.65,
                'gender': 'F',
                'phone': '(11) 91234-5678',
                'email': 'ana.silva@email.com',
                'notes': 'Queixa de fascite plantar bilateral.',
            },
            {
                'name': 'João Pedro Oliveira',
                'birth_date': '1978-11-02',
                'weight_kg': 95.0,
                'height_m': 1.80,
                'gender': 'M',
                'phone': '(21) 99887-6655',
                'notes': 'Pé plano adquirido, em tratamento.',
            },
            {
                'name': 'Beatriz Fernandes Costa',
                'birth_date': '2000-07-14',
                'weight_kg': 58.0,
                'height_m': 1.68,
                'gender': 'F',
                'phone': '(31) 98877-4433',
                'email': 'bia.costa@email.com',
                'notes': 'Atleta amadora, avaliação de pisada para corrida.',
            },
            {
                'name': 'Ricardo Almeida Souza',
                'birth_date': '1965-01-30',
                'weight_kg': 88.0,
                'height_m': 1.72,
                'gender': 'M',
                'phone': '(41) 97766-5544',
                'notes': 'Diabético, avaliação de risco de úlceras plantares.',
            },
        ]

        patients = []
        for pdata in patients_data:
            patient, _ = Patient.objects.get_or_create(
                name=pdata['name'],
                defaults=pdata,
            )
            patients.append(patient)
            self.stdout.write(self.style.SUCCESS(f'  Paciente: {patient.name}'))

        # 3) Exames (pelo menos 1 por paciente, alguns com mais de um)
        exams = []
        exam_configs = [
            (patients[0], 'STATIC',   -5),    # Marcos - estática
            (patients[0], 'DYNAMIC',  -3),    # Marcos - dinâmica
            (patients[1], 'STATIC',   -10),   # Ana
            (patients[1], 'STABILOMETRY', -2),# Ana - estabilometria
            (patients[2], 'DYNAMIC',  -7),    # João
            (patients[3], 'STATIC',   -15),   # Beatriz
            (patients[4], 'STATIC',   -1),    # Ricardo
        ]

        for patient, etype, days_offset in exam_configs:
            exam_date = timezone.now() + timedelta(days=days_offset, hours=-random.randint(1, 10))
            exam, _ = Exam.objects.get_or_create(
                patient=patient,
                exam_type=etype,
                exam_date__date=exam_date.date(),
                defaults={
                    'doctor': doctor,
                    'exam_date': exam_date,
                    'footwear': 'Descalço',
                    'notes': f'Exame de {patient.name} - {etype}',
                }
            )
            exams.append(exam)

        # 4) Para cada exame, gerar FootAnalysis, PressureSnapshot, PressureDistribution
        for exam in exams:
            self._create_foot_analyses(exam)
            self._create_pressure_snapshots(exam)
            self._create_pressure_distribution(exam)
            if exam.exam_type == 'STABILOMETRY':
                self._create_stabilometry(exam)

        # 5) Calibração dos sensores (grid completo)
        sensor_count = 0
        for r in range(settings.SENSOR_GRID_ROWS):
            for c in range(settings.SENSOR_GRID_COLS):
                sid = r * settings.SENSOR_GRID_COLS + c
                SensorCalibration.objects.get_or_create(
                    sensor_id=sid,
                    defaults={
                        'row': r, 'col': c,
                        'offset': random.uniform(-0.01, 0.01),
                        'gain': random.uniform(0.95, 1.05),
                        'is_active': random.random() > 0.02,
                    }
                )
                sensor_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'População concluída! {sensor_count} sensores calibrados.'
        ))

    # ---------- helpers ----------

    def _create_foot_analyses(self, exam):
        # Valores baseados no PDF do Marcos
        FootAnalysis.objects.get_or_create(
            exam=exam, side='L',
            defaults={
                'surface_cm2': 96.44,
                'max_pressure_kgf_cm2': 0.60,
                'avg_pressure_kgf_cm2': 0.20,
                'load_percentage': random.uniform(46, 54),
            }
        )
        FootAnalysis.objects.get_or_create(
            exam=exam, side='R',
            defaults={
                'surface_cm2': 96.44,
                'max_pressure_kgf_cm2': 0.60,
                'avg_pressure_kgf_cm2': 0.22,
                'load_percentage': random.uniform(46, 54),
            }
        )

    def _create_pressure_snapshots(self, exam, n_frames=5):
        """Cria alguns snapshots de pressão simulados."""
        for frame in range(n_frames):
            for side in ['L', 'R']:
                matrix = self._simulate_foot_matrix(
                    settings.SENSOR_GRID_ROWS,
                    settings.SENSOR_GRID_COLS,
                    frame=frame,
                    side=side,
                )
                PressureSnapshot.objects.get_or_create(
                    exam=exam,
                    side=side,
                    frame_index=frame,
                    defaults={
                        'pressure_matrix': matrix.tolist(),
                        'captured_at': exam.exam_date + timedelta(seconds=frame),
                    }
                )

    def _simulate_foot_matrix(self, rows, cols, frame=0, side='L'):
        """Gera uma matriz simulando a pisada de um pé."""
        matrix = np.zeros((rows, cols))
        y, x = np.ogrid[0:rows, 0:cols]

        # Calcanhar
        heel_cx, heel_cy = cols // 2, int(rows * 0.85)
        heel = 0.6 * np.exp(-((x - heel_cx) ** 2 + (y - heel_cy) ** 2) / 30)

        # Metatarso medial
        meta_med_cx = int(cols * 0.35) if side == 'L' else int(cols * 0.65)
        meta_med_cy = int(rows * 0.2)
        meta_med = 0.55 * np.exp(-((x - meta_med_cx) ** 2 + (y - meta_med_cy) ** 2) / 15)

        # Metatarso lateral
        meta_lat_cx = int(cols * 0.65) if side == 'L' else int(cols * 0.35)
        meta_lat_cy = int(rows * 0.22)
        meta_lat = 0.4 * np.exp(-((x - meta_lat_cx) ** 2 + (y - meta_lat_cy) ** 2) / 18)

        # Arco
        arch_cx, arch_cy = int(cols * 0.55), int(rows * 0.5)
        arch = 0.15 * np.exp(-((x - arch_cx) ** 2 + (y - arch_cy) ** 2) / 40)

        matrix = heel + meta_med + meta_lat + arch
        noise = np.random.normal(0, 0.02, matrix.shape)
        matrix = np.clip(matrix + noise, 0, 1.0)
        return matrix

    def _create_pressure_distribution(self, exam):
        distributions = [
            ('ANTERIOR', random.uniform(40, 55)),
            ('POSTERIOR', random.uniform(40, 55)),
            ('LATERAL', random.uniform(45, 55)),
            ('MEDIAL', random.uniform(45, 55)),
        ]
        for region, pct in distributions:
            PressureDistribution.objects.get_or_create(
                exam=exam, region=region,
                defaults={'percentage': round(pct, 2)}
            )

    def _create_stabilometry(self, exam):
        """Baseado nos dados do PDF do Marcos."""
        StabilometryResult.objects.get_or_create(
            exam=exam,
            defaults={
                'path_length_mm': 108.65,
                'area_mm2': 78.32,
                'extension_area_ratio': 1.39,
                'avg_velocity_mm_s': 3.62,
                'sway_left': 46.16,
                'sway_right': 53.84,
                'sway_anterior': 47.07,
                'sway_posterior': 52.93,
            }
        )