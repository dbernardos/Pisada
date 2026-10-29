"""
Gera os ícones do PWA a partir do logo do sistema.

Uso (na raiz do projeto):
    pip install pillow
    python make_icons.py core/static/core/images/logo.png

Cria, na mesma pasta do logo:
    icon-192x192.png            ícone padrão
    icon-512x512.png            ícone padrão
    icon-maskable-512x512.png   com margem de segurança (o Android recorta em círculo/squircle)
"""
import sys
from pathlib import Path

from PIL import Image

BACKGROUND = (15, 23, 42, 255)  # #0f172a, a mesma cor do tema


def make_icon(logo, size, content_ratio):
    """Centraliza o logo num quadrado de fundo sólido ocupando `content_ratio` do lado."""
    canvas = Image.new('RGBA', (size, size), BACKGROUND)
    box = int(size * content_ratio)
    scale = min(box / logo.width, box / logo.height)
    resized = logo.resize((max(1, int(logo.width * scale)), max(1, int(logo.height * scale))), Image.LANCZOS)
    canvas.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas.convert('RGB')


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    logo_path = Path(sys.argv[1])
    logo = Image.open(logo_path).convert('RGBA')
    out = logo_path.parent

    make_icon(logo, 192, 0.72).save(out / 'icon-192x192.png')
    make_icon(logo, 512, 0.72).save(out / 'icon-512x512.png')
    make_icon(logo, 512, 0.56).save(out / 'icon-maskable-512x512.png')  # zona segura: ~80% central
    print('Ícones gerados em', out)


if __name__ == '__main__':
    main()
