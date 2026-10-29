/**
 * Desenha uma matriz de pressão em um canvas como mapa de calor.
 * @param {CanvasRenderingContext2D} ctx
 * @param {HTMLCanvasElement} canvas
 * @param {number[][]} matrix - matriz rows x cols com valores 0..1
 * @param {number} rows
 * @param {number} cols
 */
function drawHeatmap(ctx, canvas, matrix, rows, cols) {
    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    // Fundo com formato aproximado de pé
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, W, H);

    if (!matrix || matrix.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Aguardando dados...', W / 2, H / 2);
        return;
    }

    const cellW = W / cols;
    const cellH = H / rows;

    // Desenha máscara de pé (elipses sobrepostas)
    ctx.save();
    ctx.beginPath();
    // Metatarso (parte superior larga)
    ctx.ellipse(W / 2, H * 0.22, W * 0.45, H * 0.18, 0, 0, Math.PI * 2);
    // Arco
    ctx.ellipse(W * 0.55, H * 0.5, W * 0.30, H * 0.22, 0, 0, Math.PI * 2);
    // Calcanhar (parte inferior)
    ctx.ellipse(W / 2, H * 0.85, W * 0.32, H * 0.14, 0, 0, Math.PI * 2);
    ctx.clip();

    // Desenha a matriz
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const value = matrix[r][c];
            ctx.fillStyle = pressureToColor(value);
            ctx.fillRect(c * cellW, r * cellH, cellW + 1, cellH + 1);
        }
    }
    ctx.restore();

    // Contorno do pé
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(W / 2, H * 0.22, W * 0.45, H * 0.18, 0, 0, Math.PI * 2);
    ctx.ellipse(W * 0.55, H * 0.5, W * 0.30, H * 0.22, 0, 0, Math.PI * 2);
    ctx.ellipse(W / 2, H * 0.85, W * 0.32, H * 0.14, 0, 0, Math.PI * 2);
    ctx.stroke();
}

/**
 * Converte um valor de pressão (0..1) em cor (azul → verde → amarelo → vermelho).
 */
function pressureToColor(value) {
    const v = Math.max(0, Math.min(1, value));
    let r, g, b;

    if (v < 0.25) {
        // Azul → Ciano
        const t = v / 0.25;
        r = 0;
        g = Math.round(255 * t);
        b = 255;
    } else if (v < 0.5) {
        // Ciano → Verde
        const t = (v - 0.25) / 0.25;
        r = 0;
        g = 255;
        b = Math.round(255 * (1 - t));
    } else if (v < 0.75) {
        // Verde → Amarelo
        const t = (v - 0.5) / 0.25;
        r = Math.round(255 * t);
        g = 255;
        b = 0;
    } else {
        // Amarelo → Vermelho
        const t = (v - 0.75) / 0.25;
        r = 255;
        g = Math.round(255 * (1 - t));
        b = 0;
    }
    return `rgb(${r},${g},${b})`;
}