"""
Comando para simular o envio de dados do ESP32 via WebSocket.
Use quando quiser testar o dashboard sem o hardware real.

Uso:
    python manage.py simulate_esp32
"""
import json
import time
import numpy as np
from django.core.management.base import BaseCommand
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class Command(BaseCommand):
    help = 'Simula o ESP32 enviando frames de pressão via Channel Layer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--frames', type=int, default=200,
            help='Número de frames a gerar (0 = infinito)'
        )
        parser.add_argument(
            '--fps', type=int, default=10,
            help='Frames por segundo'
        )

    def handle(self, *args, **options):
        rows = settings.SENSOR_GRID_ROWS
        cols = settings.SENSOR_GRID_COLS
        channel_layer = get_channel_layer()
        group = 'simulation'
        frame = 0
        max_frames = options['frames']
        interval = 1.0 / options['fps']

        self.stdout.write(
            f'Iniciando simulação ESP32 ({rows}x{cols}, {options["fps"]} FPS)...'
        )
        self.stdout.write('Pressione Ctrl+C para parar.')

        try:
            while max_frames == 0 or frame < max_frames:
                matrix = self._generate_frame(rows, cols, frame)
                message = {
                    'type': 'simulation.frame',
                    'frame': frame,
                    'rows': rows,
                    'cols': cols,
                    'matrix': matrix.tolist(),
                }
                async_to_sync(channel_layer.group_send)(group, message)
                frame += 1
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nSimulação interrompida.'))

    def _generate_frame(self, rows, cols, frame):
        matrix = np.zeros((rows, cols))
        y, x = np.ogrid[0:rows, 0:cols]
        phase = (frame % 60) / 60.0 * 2 * np.pi

        heel = max(0, np.cos(phase)) * 0.6
        heel_cx, heel_cy = cols // 2, int(rows * 0.85)
        m1 = heel * np.exp(-((x - heel_cx) ** 2 + (y - heel_cy) ** 2) / 30)

        meta = max(0, np.cos(phase + np.pi)) * 0.55
        meta_cx, meta_cy = int(cols * 0.4), int(rows * 0.2)
        m2 = meta * np.exp(-((x - meta_cx) ** 2 + (y - meta_cy) ** 2) / 15)

        arch_cx, arch_cy = int(cols * 0.55), int(rows * 0.5)
        m3 = 0.1 * np.exp(-((x - arch_cx) ** 2 + (y - arch_cy) ** 2) / 40)

        matrix = m1 + m2 + m3
        noise = np.random.normal(0, 0.015, matrix.shape)
        return np.clip(matrix + noise, 0, 1.0)