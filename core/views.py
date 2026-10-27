from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# from .serializers import LeituraPalmilhaSerializer

from django.shortcuts import render, get_object_or_404
from .models import Paciente, ExamePalmilha
# from .models import LeituraSensorESP32

def pacientes_view(request):
    """Lista todos os pacientes cadastrados no banco"""
    pacientes = Paciente.objects.prefetch_related('exames').all()
    return render(request, 'palmilha/pacientes.html', {'pacientes': pacientes})

def historico_view(request):
    """Lista todos os exames realizados armazenados no banco"""
    exames = ExamePalmilha.objects.select_related('paciente').order_by('-data_hora')
    return render(request, 'palmilha/historico.html', {'exames': exames})

def dashboard_view(request, exame_id=None):
    """
    Exibe o dashboard de análise. 
    Se um ID de exame for passado, mostra ele. Caso contrário, pega o último exame cadastrado.
    """
    if exame_id:
        exame_atual = get_object_or_404(ExamePalmilha, id=exame_id)
    else:
        exame_atual = ExamePalmilha.objects.select_related('paciente').last()

    # Última leitura de sensores bruta do ESP32 para esse exame (se houver)
    ultima_leitura = None
    if exame_atual:
        ultima_leitura = exame_atual.leituras_sensores.last()

    context = {
        'exame': exame_atual,
        'paciente': exame_atual.paciente if exame_atual else None,
        'leitura_sensor': ultima_leitura,
    }
    return render(request, 'palmilha/dashboard.html', context)