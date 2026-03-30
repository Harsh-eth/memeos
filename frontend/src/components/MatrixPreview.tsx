import { useEffect, useRef } from "react";
import { drawMatrix } from "../lib/matrixDraw";

type MatrixPreviewProps = {
  width: number;
  height: number;
  seed?: number;
  className?: string;
};

/** Static-looking matrix code block for mock thumbnails and main output. */
export function MatrixPreview({ width, height, seed = 0, className = "" }: MatrixPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    drawMatrix(ctx, width, height, seed);
  }, [width, height, seed]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ display: "block", verticalAlign: "top" }}
    />
  );
}
