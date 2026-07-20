/** A four-point sparkle star centered on (cx, cy). Shared by the Mascot SVG
 *  layers and the container-scale BackdropScene (Phase 34). */
export function starPath(cx: number, cy: number, r: number): string {
  const inner = r * 0.4;
  return [
    `M${cx},${cy - r}`,
    `L${cx + inner},${cy - inner}`,
    `L${cx + r},${cy}`,
    `L${cx + inner},${cy + inner}`,
    `L${cx},${cy + r}`,
    `L${cx - inner},${cy + inner}`,
    `L${cx - r},${cy}`,
    `L${cx - inner},${cy - inner}`,
    'Z',
  ].join(' ');
}
