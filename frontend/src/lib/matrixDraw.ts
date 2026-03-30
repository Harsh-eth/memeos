export function drawMatrix(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  seed: number
): void {
  let rng = seed;
  const rand = () => {
    rng = (rng * 1103515245 + 12345) & 0x7fffffff;
    return rng / 0x7fffffff;
  };

  ctx.fillStyle = "#030712";
  ctx.fillRect(0, 0, width, height);

  const glyphs = "ｱｲｳｴｵカキクケコ01";
  const colW = 11;
  const rowH = 14;
  ctx.font = "11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";

  for (let y = 0; y < height; y += rowH) {
    for (let x = 0; x < width; x += colW) {
      const t = rand();
      const ch = glyphs[Math.floor(rand() * glyphs.length)] ?? "0";
      if (t > 0.55) ctx.fillStyle = "#2563eb";
      else if (t > 0.25) ctx.fillStyle = "#60a5fa";
      else ctx.fillStyle = "#1d4ed8";
      ctx.fillText(ch, x, y + 11);
    }
  }
}

export function matrixToPngDataUrl(width: number, height: number, seed: number): string {
  const canvas = document.createElement("canvas");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  ctx.scale(dpr, dpr);
  drawMatrix(ctx, width, height, seed);
  return canvas.toDataURL("image/png");
}
