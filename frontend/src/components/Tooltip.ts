export function attachTooltip(target: HTMLElement, text: string): void {
  if (!text) return;
  target.dataset.tooltip = text;
  if (!target.getAttribute('aria-label')) target.setAttribute('aria-label', text);
}
