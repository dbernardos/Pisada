from django.urls import path
from .views import ReceberDadosESP32, dashboard_view

urlpatterns = [
    path('api/dados-esp32/', ReceberDadosESP32.as_view(), name='api_dados_esp32'),
    path('dashboard/', dashboard_view, name='dashboard_palmilha'),
]