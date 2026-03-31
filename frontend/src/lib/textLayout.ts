import { prepare, layout } from "@chenglou/pretext";

export function layoutText(
  text: string,
  font: string,
  maxWidth: number,
  lineHeight: number,
): any {
  const prepared = prepare(text, font);
  const result = layout(prepared as any, maxWidth, lineHeight);
  return result;
}

