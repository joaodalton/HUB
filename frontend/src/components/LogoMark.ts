import { createElement } from '../dom';

function logoMarkMarkup(): string {
  return `<svg viewBox="0 20 160 90" role="img" aria-label="HUB"><path d="M106 62 A18 18 0 0 1 142 62 Z" fill="var(--accent)"></path><g stroke="var(--accent)" stroke-width="4.5" stroke-linecap="round"><line x1="112.5" y1="42.1" x2="108.5" y2="35.2"></line><line x1="124" y1="39" x2="124" y2="31"></line><line x1="135.5" y1="42.1" x2="139.5" y2="35.2"></line><line x1="143.9" y1="50.5" x2="150.8" y2="46.5"></line></g><g fill="#158dfd"><polygon points="12.92,84.19 42.47,77.86 50.44,59.55 25.78,64.07"></polygon><polygon points="46.51,77.00 76.15,70.66 78.53,54.41 53.81,58.93"></polygon><polygon points="80.19,69.80 109.74,63.47 106.56,49.27 81.90,53.79"></polygon></g><g fill="#4fc3f7"><polygon points="27.54,61.33 51.53,57.05 59.50,38.74 40.40,41.21"></polygon><polygon points="54.80,56.47 78.86,52.19 81.24,35.94 62.10,38.40"></polygon><polygon points="82.13,51.61 106.12,47.33 102.94,33.13 83.84,35.60"></polygon></g><path d="M6 98 C40 92 95 82 124 68 C136 62 144 58 146 58 C144 66 128 80 96 88 C62 97 28 102 6 98 Z" transform="translate(0 -5)" fill="#22c58e"></path></svg>`;
}

export function createLogoMark(className?: string): HTMLElement {
  const mark = createElement('span', { className });
  mark.innerHTML = logoMarkMarkup();
  return mark;
}
