from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import LeituraPalmilha
from .serializers import LeituraPalmilhaSerializer
from django.shortcuts import render

class ReceberDadosESP32(APIView) :
    """API para o ESP32 enviar os dados via POST"""
    def post(self, request) :
        serializer = LeituraPalmilhaSerializer(data=request.data)
        if serializer.is_valid() :
            serializer.save()
            return Response({"status": "sucesso", "mensagem": "Dados salvos com sucesso!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# def dashboard_view(request) :
#     """View para renderizar o front-end no Django"""
#     ultima_leitura = LeituraPalmilha.objects.last()
#     return render(request, 'palmilha/dashboard.html', {'leitura': ultima_leitura})


def dashboard_view(request):
    # Se não houver dados no banco, criamos um objeto temporário na memória para teste
    leitura = LeituraPalmilha.objects.last()
    
    if not leitura:
        leitura = LeituraPalmilha(
            paciente="Maria Silva",
            sensor_calcanhar=8.5,    # Valor alto (vermelho)
            sensor_medio_pe=3.0,     # Valor normal/baixo (verde/azul)
            sensor_antepe_lat=4.2,   # Valor moderado (amarelo)
            sensor_antepe_med=6.8,   # Valor alto (amarelo/vermelho)
            sensor_halux=9.1         # Pico de pressão (vermelho)
        )

    return render(request, 'palmilha/dashboard.html', {'leitura': leitura})