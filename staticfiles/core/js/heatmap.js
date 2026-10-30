/**
 * Desenha uma matriz de pressão em um canvas como mapa de calor suave.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {HTMLCanvasElement} canvas
 * @param {number[][]} matrix  matriz rows x cols com valores de pressão (kgf/cm²)
 * @param {number} rows
 * @param {number} cols
 * @param {Object}  [options]
 * @param {number}  [options.maxValue=1]   valor que vira vermelho máximo (ex.: 8 kgf/cm²).
 *                                         Os valores são divididos por ele antes de colorir.
 * @param {HTMLImageElement|null} [options.mask=null]
 *        Imagem com fundo transparente da planta do pé. O calor só aparece onde a imagem
 *        é opaca e a matriz é esticada sobre a área da imagem (mesmo ajuste "contain" do CSS).
 *        Sem máscara, usa um contorno aproximado feito de elipses.
 * @param {string|null} [options.background='#1a1a1a']  cor de fundo (null = transparente)
 * @param {string}  [options.placeholder='Aguardando dados...']  texto quando não há matriz
 * @param {number}  [options.blur=4]  suavização em px do canvas (0 desliga)
 */
function drawHeatmap(ctx, canvas, matrix, rows, cols, options) {
    const o = Object.assign({
        maxValue: 1,
        mask: null,
        background: '#1a1a1a',
        placeholder: 'Aguardando dados...',
        blur: 4,
    }, options);

    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    if (o.background) {
        ctx.fillStyle = o.background;
        ctx.fillRect(0, 0, W, H);
    }

    if (!matrix || matrix.length === 0) {
        _drawPlaceholder(ctx, W, H, o.placeholder);
        return;
    }

    // 1) Matriz -> imagem pequena (1 pixel por sensor). Pressão baixa fica transparente.
    const low = _scratchCanvas('low', cols, rows);
    const lowCtx = low.getContext('2d');
    const imgData = lowCtx.createImageData(cols, rows);
    const px = imgData.data;
    const maxValue = o.maxValue > 0 ? o.maxValue : 1;

    for (let r = 0; r < rows; r++) {
        const row = matrix[r] || [];
        for (let c = 0; c < cols; c++) {
            const v = Math.max(0, Math.min(1, (row[c] || 0) / maxValue));
            const [R, G, B] = pressureToRGB(v);
            const alpha = Math.min(1, Math.max(0, (v - 0.02) / 0.18)); // 0 em v<=0.02, 1 em v>=0.2
            const i = (r * cols + c) * 4;
            px[i] = R;
            px[i + 1] = G;
            px[i + 2] = B;
            px[i + 3] = Math.round(255 * 0.92 * alpha);
        }
    }
    lowCtx.putImageData(imgData, 0, 0);

    // 2) Área onde a matriz é esticada: a área da imagem (contain) ou o canvas inteiro.
    const mask = o.mask && o.mask.naturalWidth > 0 ? o.mask : null;
    const rect = mask
        ? _containRect(mask.naturalWidth, mask.naturalHeight, W, H)
        : { x: 0, y: 0, w: W, h: H };

    // 3) Camada auxiliar: matriz ampliada e suavizada.
    const layer = _scratchCanvas('layer', W, H);
    const layerCtx = layer.getContext('2d');
    layerCtx.clearRect(0, 0, W, H);
    layerCtx.imageSmoothingEnabled = true;
    layerCtx.imageSmoothingQuality = 'high';
    layerCtx.filter = o.blur > 0 ? `blur(${o.blur}px)` : 'none'; // ignorado em navegadores sem suporte
    layerCtx.drawImage(low, rect.x, rect.y, rect.w, rect.h);
    layerCtx.filter = 'none';

    // 4) Recorta no formato do pé e desenha no canvas final.
    if (mask) {
        layerCtx.globalCompositeOperation = 'destination-in';
        layerCtx.drawImage(mask, rect.x, rect.y, rect.w, rect.h);
        layerCtx.globalCompositeOperation = 'source-over';
        ctx.drawImage(layer, 0, 0);
    } else {
        ctx.save();
        _footOutlinePath(ctx, W, H);
        ctx.clip();
        ctx.drawImage(layer, 0, 0);
        ctx.restore();

        ctx.strokeStyle = '#444';
        ctx.lineWidth = 2;
        _footOutlinePath(ctx, W, H);
        ctx.stroke();
    }
}

/** Contorno aproximado do pé (usado só quando não há imagem-máscara). */
function _footOutlinePath(ctx, W, H) {
    const shapes = [
        [W / 2, H * 0.22, W * 0.45, H * 0.18],   // antepé
        [W * 0.55, H * 0.5, W * 0.30, H * 0.22], // arco
        [W / 2, H * 0.85, W * 0.32, H * 0.14],   // calcanhar
    ];
    ctx.beginPath();
    shapes.forEach(([cx, cy, rx, ry]) => {
        ctx.moveTo(cx + rx, cy); // evita linha ligando uma elipse à outra
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    });
}

/** Retângulo que uma imagem ocupa dentro do canvas com object-fit: contain. */
function _containRect(imgW, imgH, W, H) {
    const scale = Math.min(W / imgW, H / imgH);
    const w = imgW * scale;
    const h = imgH * scale;
    return { x: (W - w) / 2, y: (H - h) / 2, w, h };
}

/** Canvas auxiliar reutilizado entre frames (evita criar um novo a cada desenho). */
function _scratchCanvas(key, w, h) {
    const cache = (_scratchCanvas.cache = _scratchCanvas.cache || {});
    const c = cache[key] || (cache[key] = document.createElement('canvas'));
    if (c.width !== w) c.width = w;
    if (c.height !== h) c.height = h;
    return c;
}

function _drawPlaceholder(ctx, W, H, text) {
    if (!text) return;
    ctx.save();
    ctx.fillStyle = '#94a3b8';
    ctx.font = `${Math.max(12, Math.round(W * 0.045))}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, W / 2, H / 2);
    ctx.restore();
}

/**
 * Converte um valor normalizado (0..1) em [r, g, b]
 * (azul → ciano → verde → amarelo → vermelho).
 */
function pressureToRGB(value) {
    const v = Math.max(0, Math.min(1, value));
    let r, g, b;

    if (v < 0.25) {
        const t = v / 0.25;            // azul → ciano
        r = 0;
        g = Math.round(255 * t);
        b = 255;
    } else if (v < 0.5) {
        const t = (v - 0.25) / 0.25;   // ciano → verde
        r = 0;
        g = 255;
        b = Math.round(255 * (1 - t));
    } else if (v < 0.75) {
        const t = (v - 0.5) / 0.25;    // verde → amarelo
        r = Math.round(255 * t);
        g = 255;
        b = 0;
    } else {
        const t = (v - 0.75) / 0.25;   // amarelo → vermelho
        r = 255;
        g = Math.round(255 * (1 - t));
        b = 0;
    }
    return [r, g, b];
}

/** Versão em string CSS de pressureToRGB (mantida por compatibilidade). */
function pressureToColor(value) {
    const [r, g, b] = pressureToRGB(value);
    return `rgb(${r},${g},${b})`;
}
