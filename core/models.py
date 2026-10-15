from django.db import models

class LeituraPalmilha(models.Model) :
    data_hora = models.DateTimeField(auto_now_add=True)
    paciente = models.CharField(max_length=100, default="Paciente Teste")
    
    # Exemplo considerando 6 sensores principais na palmilha (calcanhar, médio-pé, antepé, hálux, etc.)
    sensor_calcanhar = models.FloatField(default=0.0)
    sensor_medio_pe = models.FloatField(default=0.0)
    sensor_antepe_lat = models.FloatField(default=0.0)
    sensor_antepe_med = models.FloatField(default=0.0)
    sensor_halux = models.FloatField(default=0.0)
    sensor_dedos = models.FloatField(default=0.0)

    def __str__(self) :
        return f"Leitura de {self.paciente} em {self.data_hora.strftime('%d/%m/%Y %H:%M:%S')}"