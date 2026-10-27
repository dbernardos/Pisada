from django.db import models

class Paciente(models.Model):
    nome = models.CharField(max_length=100)
    data_nascimento = models.DateField()
    calcado = models.CharField(max_length=20, blank=True, null=True) # Ex: "41/42"
    peso = models.FloatField(help_text="Peso em kg", blank=True, null=True)
    estatura = models.FloatField(help_text="Estatura em cm", blank=True, null=True)
    tipo_pe = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.nome

class ExamePalmilha(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='exames')
    data_hora = models.DateTimeField(auto_now_add=True)
    profissional_responsavel = models.CharField(max_length=100)
    tipo_exame = models.CharField(max_length=50, default="Análise Dinâmica")

    # --- Dados por Membro (Pé Esquerdo e Direito) ---
    # Pé Esquerdo
    pe_esq_superficie = models.FloatField(default=0.0, help_text="Superfície em cm²")
    pe_esq_p_max = models.FloatField(default=0.0, help_text="Pressão máxima kg/cm²")
    pe_esq_p_med = models.FloatField(default=0.0, help_text="Pressão média kg/cm²")

    # Pé Direito
    pe_dir_superficie = models.FloatField(default=0.0, help_text="Superfície em cm²")
    pe_dir_p_max = models.FloatField(default=0.0, help_text="Pressão máxima kg/cm²")
    pe_dir_p_med = models.FloatField(default=0.0, help_text="Pressão média kg/cm²")

    # --- Distribuição da Pressão ---
    dist_antero_posterior = models.CharField(max_length=50, blank=True, null=True) # Ex: "Antépe 55% / Retropé 45%"
    dist_lateral = models.CharField(max_length=50, blank=True, null=True)          # Ex: "Medial 48% / Lateral 52%"
    dist_membro = models.CharField(max_length=50, blank=True, null=True)           # Ex: "Esquerdo 48% / Direito 52%"

    # --- Estabilometria ---
    estabilometria_corpo = models.CharField(max_length=50, blank=True, null=True)
    comprimento_trajeto = models.FloatField(default=0.0, help_text="mm")
    area_estabilometria = models.FloatField(default=0.0, help_text="mm²")
    extensao_area = models.FloatField(default=0.0, blank=True, null=True)
    velocidade_media = models.FloatField(default=0.0, help_text="mm/s")
    estabilometria_pe_esq = models.FloatField(default=0.0, blank=True, null=True)
    estabilometria_pe_dir = models.FloatField(default=0.0, blank=True, null=True)

    def __str__(self):
        return f"Exame de {self.paciente.nome} em {self.data_hora.strftime('%d/%m/%Y %H:%M')}"


class LeituraSensorESP32(models.Model):
    """Armazena os dados brutos enviados pelo microcontrolador a cada ciclo de leitura"""
    exame = models.ForeignKey(ExamePalmilha, on_delete=models.CASCADE, related_name='leituras_sensores', null=True, blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)
    
    # Sensores individuais da palmilha (exemplo com 6 pontos principais por pé)
    # Esquerdo
    esq_calcanhar = models.FloatField(default=0.0)
    esq_medio_pe = models.FloatField(default=0.0)
    esq_antepe = models.FloatField(default=0.0)
    esq_halux = models.FloatField(default=0.0)
    
    # Direito
    dir_calcanhar = models.FloatField(default=0.0)
    dir_medio_pe = models.FloatField(default=0.0)
    dir_antepe = models.FloatField(default=0.0)
    dir_halux = models.FloatField(default=0.0)

    def __str__(self):
        return f"Leitura ESP32 - {self.data_hora.strftime('%H:%M:%S.%f')}"