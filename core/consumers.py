import json
import asyncio
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


class SimulationConsumer(AsyncWebsocketConsumer):
    """WebSocket que envia frames simulados do ESP32 em tempo real."""

    async def connect(self):
        await self.accept()
        self.running = True
        asyncio.create_task(self._stream_frames())

    async def disconnect(self, close_code):
        self.running = False

    async def _stream_frames(self):
        rows = settings.SENSOR_GRID_ROWS
        cols = settings.SENSOR_GRID_COLS
        frame = 0

        while self.running:
            matrix = self._generate_frame(rows, cols, frame)
            await self.send(text_data=json.dumps({
                'frame': frame,
                'rows': rows,
                'cols': cols,
                'matrix': matrix.tolist(),
            }))
            frame += 1
            await asyncio.sleep(0.1)  # 10 FPS

    def _generate_frame(self, rows, cols, frame):
        matrix = np.zeros((rows, cols))
        y, x = np.ogrid[0:rows, 0:cols]

        # Fase do ciclo da pisada (0 a 2π)
        phase = (frame % 60) / 60.0 * 2 * np.pi

        # Calcanhar (contato inicial)
        heel_intensity = max(0, np.cos(phase)) * 0.6
        heel_cx, heel_cy = cols // 2, int(rows * 0.85)
        heel = heel_intensity * np.exp(-((x - heel_cx) ** 2 + (y - heel_cy) ** 2) / 30)

        # Metatarso (impulsão)
        meta_intensity = max(0, np.cos(phase + np.pi)) * 0.55
        meta_cx, meta_cy = int(cols * 0.4), int(rows * 0.2)
        meta = meta_intensity * np.exp(-((x - meta_cx) ** 2 + (y - meta_cy) ** 2) / 15)

        # Arco médio
        arch_cx, arch_cy = int(cols * 0.55), int(rows * 0.5)
        arch = 0.1 * np.exp(-((x - arch_cx) ** 2 + (y - arch_cy) ** 2) / 40)

        matrix = heel + meta + arch
        noise = np.random.normal(0, 0.015, matrix.shape)
        matrix = np.clip(matrix + noise, 0, 1.0)
        return matrix