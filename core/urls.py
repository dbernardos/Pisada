from django.urls import path
from .views import dashboard_view, pacientes_view, historico_view

urlpatterns = [
    # path('api/dados-esp32/', ReceberDadosESP32.as_view(), name='api_dados_esp32'),
    path('dashboard/', dashboard_view, name='dashboard_palmilha'),
    path('pacientes/', pacientes_view, name='pacientes'),
    path('historico/', historico_view, name='historico'),
    path('dashboard/<int:exame_id>/', dashboard_view, name='dashboard_detalhe'),
]