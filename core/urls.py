from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pacientes/', views.patients_list, name='patients_list'),
    path('pacientes/novo/', views.patient_create, name='patient_create'),
    path('pacientes/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('pacientes/<int:pk>/editar/', views.patient_edit, name='patient_edit'),
    path('historico/', views.history, name='history'),
    path('exames/<int:pk>/', views.exam_detail, name='exam_detail'),
    path('exames/<int:pk>/relatorio.pdf', views.exam_report_pdf, name='exam_report_pdf'),
    
    path('sw.js', views.service_worker, name='service_worker'),
    path('manifest.json', views.manifest, name='manifest'),
    path('offline/', views.offline, name='offline'),
    
    # APIs
    path('api/exames/<int:exam_id>/snapshot/',
         views.api_latest_snapshot, name='api_latest_snapshot'),
    path('api/simulate/frame/',
         views.api_simulate_frame, name='api_simulate_frame'),
]