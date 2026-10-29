from django.contrib import admin
from .models import (
    Patient, Doctor, Exam, FootAnalysis,
    PressureSnapshot, StabilometryResult,
    PressureDistribution, SensorCalibration,
)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'birth_date', 'age', 'weight_kg', 'gender')
    search_fields = ('name', 'email', 'phone')


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'crefito', 'specialty')


class FootAnalysisInline(admin.TabularInline):
    model = FootAnalysis
    extra = 0


class PressureDistributionInline(admin.TabularInline):
    model = PressureDistribution
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('patient', 'exam_type', 'exam_date', 'doctor')
    list_filter = ('exam_type', 'exam_date')
    search_fields = ('patient__name',)
    inlines = [FootAnalysisInline, PressureDistributionInline]


@admin.register(PressureSnapshot)
class PressureSnapshotAdmin(admin.ModelAdmin):
    list_display = ('exam', 'side', 'frame_index', 'captured_at')
    list_filter = ('side',)


@admin.register(StabilometryResult)
class StabilometryResultAdmin(admin.ModelAdmin):
    list_display = ('exam', 'path_length_mm', 'area_mm2', 'avg_velocity_mm_s')


@admin.register(SensorCalibration)
class SensorCalibrationAdmin(admin.ModelAdmin):
    list_display = ('sensor_id', 'row', 'col', 'gain', 'is_active')