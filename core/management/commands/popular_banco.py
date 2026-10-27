from django.core.management.base import BaseCommand
from core.models import Paciente, ExamePalmilha, LeituraSensorESP32
from datetime import date, datetime

class Command(BaseCommand):
    help = 'Popula o banco de dados com pacientes e exames simulados para testes.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Limpando dados antigos...')
        LeituraSensorESP32.objects.all().delete()
        ExamePalmilha.objects.all().delete()
        Paciente.objects.all().delete()

        self.stdout.write('Criando pacientes de teste...')
        
        p1 = Paciente.objects.create(
            nome="Maria Silva",
            data_nascimento=date(1990, 5, 12),
            calcado="37",
            peso=65.5,
            estatura=168.0,
            tipo_pe="Neutro (tendência Pronada)"
        )

        p2 = Paciente.objects.create(
            nome="Carlos Oliveira",
            data_nascimento=date(1982, 11, 20),
            calcado="42",
            peso=82.0,
            estatura=178.0,
            tipo_pe="Plano (Valgo)"
        )

        self.stdout.write('Criando exames associados...')
        
        exame1 = ExamePalmilha.objects.create(
            paciente=p1,
            profissional_responsavel="Dr. João Fisioterapeuta",
            tipo_exame="Análise Dinâmica",
            pe_esq_superficie=115.4,
            pe_esq_p_max=8.2,
            pe_esq_p_med=4.1,
            pe_dir_superficie=120.1,
            pe_dir_p_max=9.8,
            pe_dir_p_med=4.6,
            dist_antero_posterior="Antépe 52% / Retropé 48%",
            dist_lateral="Medial 45% / Lateral 55%",
            dist_membro="Esquerdo 48% / Direito 52%",
            estabilometria_corpo="Normal",
            comprimento_trajeto=245.2,
            area_estabilometria=112.5,
            extensao_area=45.0,
            velocidade_media=12.4,
            estabilometria_pe_esq=49.0,
            estabilometria_pe_dir=51.0
        )

        # Criando leituras simuladas do ESP32 vinculadas ao exame
        for i in range(5):
            LeituraSensorESP32.objects.create(
                exame=exame1,
                esq_calcanhar=7.5 + i,
                esq_medio_pe=3.1,
                esq_antepe=6.0,
                esq_halux=5.5,
                dir_calcanhar=9.2,
                dir_medio_pe=4.0,
                dir_antepe=7.8,
                dir_halux=6.2
            )

        self.stdout.write(self.style.SUCCESS('Banco populado com sucesso com dados simulados!'))