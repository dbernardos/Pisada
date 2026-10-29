from django.db import models
from django.conf import settings
from django.utils import timezone


class Patient(models.Model):
    """Paciente avaliado no exame de baropodometria."""
    name = models.CharField('Nome', max_length=200)
    birth_date = models.DateField('Data de nascimento')
    weight_kg = models.FloatField('Peso (kg)', null=True, blank=True)
    height_m = models.FloatField('Altura (m)', null=True, blank=True)
    gender = models.CharField(
        'Sexo',
        max_length=1,
        choices=[('M', 'Masculino'), ('F', 'Feminino'), ('O', 'Outro')],
        default='M'
    )
    phone = models.CharField('Telefone', max_length=20, blank=True)
    email = models.EmailField('E-mail', blank=True)
    notes = models.TextField('Observações clínicas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def age(self):
        today = timezone.now().date()
        born = self.birth_date
        return today.year - born.year - (
            (today.month, today.day) < (born.month, born.day)
        )

    @property
    def bmi(self):
        if self.weight_kg and self.height_m:
            return round(self.weight_kg / (self.height_m ** 2), 2)
        return None


class Doctor(models.Model):
    """Profissional responsável pelo exame."""
    name = models.CharField('Nome', max_length=200)
    crefito = models.CharField('CREFITO', max_length=50, unique=True)
    specialty = models.CharField('Especialidade', max_length=200, blank=True)
    # Identidade usada no cabeçalho e no fim do relatório em PDF
    report_title = models.CharField(
        'Título do relatório', max_length=200, blank=True,
        help_text='Ex.: "Drº Pedro Felipe Santos". Vazio = "Dr(a). <nome>".'
    )
    report_subtitle = models.TextField(
        'Subtítulo do relatório', blank=True,
        help_text='Uma linha por quebra de linha. Ex.: especialidades da clínica. Vazio = especialidade.'
    )
    signature = models.ImageField(
        'Assinatura', upload_to='signatures/', null=True, blank=True,
        help_text='PNG com fundo transparente, impresso no fim do relatório.'
    )

    class Meta:
        verbose_name = 'Profissional'
        verbose_name_plural = 'Profissionais'

    def __str__(self):
        return f"{self.name} - {self.crefito}"


class Exam(models.Model):
    """Exame de baropodometria realizado."""
    EXAM_TYPES = [
        ('STATIC', 'Estática'),
        ('DYNAMIC', 'Dinâmica'),
        ('STABILOMETRY', 'Estabilometria'),
    ]

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE,
        related_name='exams', verbose_name='Paciente'
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.SET_NULL,
        null=True, related_name='exams', verbose_name='Profissional'
    )
    exam_type = models.CharField(
        'Tipo de exame', max_length=20,
        choices=EXAM_TYPES, default='STATIC'
    )
    exam_date = models.DateTimeField('Data do exame', default=timezone.now)
    footwear = models.CharField('Calçado', max_length=100, blank=True)
    notes = models.TextField('Observações', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Exame'
        verbose_name_plural = 'Exames'
        ordering = ['-exam_date']

    def __str__(self):
        return f"{self.patient.name} - {self.get_exam_type_display()} ({self.exam_date:%d/%m/%Y})"


class FootAnalysis(models.Model):
    """Análise individual por pé (esquerdo/direito)."""
    SIDE_CHOICES = [('L', 'Esquerdo'), ('R', 'Direito')]

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE,
        related_name='foot_analyses', verbose_name='Exame'
    )
    side = models.CharField('Lado', max_length=1, choices=SIDE_CHOICES)
    surface_cm2 = models.FloatField('Superfície (cm²)')
    max_pressure_kgf_cm2 = models.FloatField('Pressão máxima (kgf/cm²)')
    avg_pressure_kgf_cm2 = models.FloatField('Pressão média (kgf/cm²)')
    load_percentage = models.FloatField(
        'Carga (%)',
        help_text='Percentual de carga suportada pelo pé'
    )

    class Meta:
        verbose_name = 'Análise do Pé'
        verbose_name_plural = 'Análises dos Pés'
        unique_together = ['exam', 'side']

    def __str__(self):
        return f"{self.exam} - {self.get_side_display()}"


class PressureSnapshot(models.Model):
    """
    Snapshot de leitura dos sensores da palmilha em um instante.
    Armazena a matriz de pressão completa (GRID_ROWS x GRID_COLS) para cada pé.
    """
    SIDE_CHOICES = [('L', 'Esquerdo'), ('R', 'Direito')]

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE,
        related_name='pressure_snapshots', verbose_name='Exame'
    )
    side = models.CharField('Lado', max_length=1, choices=SIDE_CHOICES)
    captured_at = models.DateTimeField('Capturado em', default=timezone.now)
    # Matriz armazenada como JSON: lista de listas (rows x cols) de floats (kgf/cm²)
    pressure_matrix = models.JSONField('Matriz de pressão')
    frame_index = models.PositiveIntegerField('Frame', default=0)

    class Meta:
        verbose_name = 'Snapshot de Pressão'
        verbose_name_plural = 'Snapshots de Pressão'
        ordering = ['captured_at']

    def __str__(self):
        return f"{self.exam} - {self.get_side_display()} - frame {self.frame_index}"


class StabilometryResult(models.Model):
    """Resultados da estabilometria (equilíbrio postural)."""
    exam = models.OneToOneField(
        Exam, on_delete=models.CASCADE,
        related_name='stabilometry', verbose_name='Exame'
    )
    path_length_mm = models.FloatField('Comprimento do trajeto (mm)')
    area_mm2 = models.FloatField('Área (mm²)')
    extension_area_ratio = models.FloatField('Extensão/Área (1/mm)')
    avg_velocity_mm_s = models.FloatField('Velocidade média (mm/s)')
    sway_left = models.FloatField('Balanço esquerda (%)', default=0)
    sway_right = models.FloatField('Balanço direita (%)', default=0)
    sway_anterior = models.FloatField('Balanço anterior (%)', default=0)
    sway_posterior = models.FloatField('Balanço posterior (%)', default=0)

    # Trajetória do centro de pressão (CoP) usada nos gráficos do relatório.
    # Formato: {"x": [mm, ...], "y": [mm, ...]}  (x+ = direita, y+ = anterior), uma amostra por leitura.
    sample_rate_hz = models.FloatField('Taxa de amostragem (Hz)', default=10.0)
    cop_body = models.JSONField('Trajetória do CoP - corpo', null=True, blank=True)
    cop_left = models.JSONField('Trajetória do CoP - pé esquerdo', null=True, blank=True)
    cop_right = models.JSONField('Trajetória do CoP - pé direito', null=True, blank=True)

    class Meta:
        verbose_name = 'Resultado de Estabilometria'
        verbose_name_plural = 'Resultados de Estabilometria'

    def __str__(self):
        return f"Estabilometria - {self.exam}"


class PressureDistribution(models.Model):
    """Distribuição de pressão por região do pé."""
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE,
        related_name='pressure_distributions', verbose_name='Exame'
    )
    region = models.CharField(
        'Região',
        max_length=30,
        choices=[
            ('ANTERIOR', 'Anterior'),
            ('MEDIO', 'Médio'),
            ('POSTERIOR', 'Posterior'),
            ('LATERAL', 'Lateral'),
            ('MEDIAL', 'Medial'),
        ]
    )
    percentage = models.FloatField('Percentual (%)')

    class Meta:
        verbose_name = 'Distribuição de Pressão'
        verbose_name_plural = 'Distribuições de Pressão'

    def __str__(self):
        return f"{self.exam} - {self.region}: {self.percentage}%"


class SensorCalibration(models.Model):
    """Calibração dos sensores da palmilha."""
    sensor_id = models.PositiveIntegerField('ID do sensor', unique=True)
    row = models.PositiveIntegerField('Linha')
    col = models.PositiveIntegerField('Coluna')
    offset = models.FloatField('Offset', default=0.0)
    gain = models.FloatField('Ganho', default=1.0)
    is_active = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Calibração de Sensor'
        verbose_name_plural = 'Calibrações de Sensores'

    def __str__(self):
        return f"Sensor {self.sensor_id} ({self.row},{self.col})"