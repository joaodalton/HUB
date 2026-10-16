// frontend/src/components/BrandLogo.ts
// Logos de marca simplificados, cores fixas (nao currentColor) -- usados so para
// identificar com qual servico externo o HUB se integra, sem copiar o asset oficial
// pixel-perfect e sem hotlink de imagem externa.
import { createElement } from '../dom';

export type BrandName = 'resend' | 'asaas' | 'whatsapp' | 'google';

const markup: Record<BrandName, string> = {
  resend: '<svg viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="#000"/><path d="M7 6.5h6.2a4 4 0 0 1 0 8H10l4.5 3H11l-4-3V6.5z" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  asaas: '<svg viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="#0A4EE4"/><path d="M7 16 12 6l5 10" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 13h6" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>',
  whatsapp: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="12" fill="#25D366"/><path d="M12 5.5a6.5 6.5 0 0 0-5.6 9.8L5.5 18.5l3.3-.9A6.5 6.5 0 1 0 12 5.5z" fill="#fff"/><path d="M9.6 9.3c.2-.4.4-.4.6-.4h.5c.2 0 .4 0 .5.4.2.4.6 1.4.6 1.5s0 .2-.1.3c-.2.3-.4.4-.6.6-.1.1-.2.2-.1.4.3.6.8 1.1 1.3 1.5.5.4 1 .6 1.2.7.2.1.3.1.4-.1l.6-.7c.1-.2.3-.2.5-.1l1.3.6c.2.1.3.2.3.3 0 .2 0 .9-.3 1.2-.3.3-1 .6-1.6.6-.6 0-1.6-.2-3-1.4-1.7-1.5-2.8-3.3-2.9-3.5-.1-.2-.8-1.1-.8-2.1 0-1 .5-1.5.7-1.7z" fill="#25D366"/></svg>',
  google: '<svg viewBox="0 0 24 24"><path d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v4h5.4a4.7 4.7 0 0 1-2 3.1v2.6h3.3c1.9-1.8 3-4.4 3-7.7z" fill="#4285F4"/><path d="M12 22c2.7 0 5-.9 6.7-2.4l-3.3-2.6c-.9.6-2.1 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H2.9v2.6A10 10 0 0 0 12 22z" fill="#34A853"/><path d="M6.4 13.9A6 6 0 0 1 6.1 12c0-.6.1-1.3.3-1.9V7.5H2.9A10 10 0 0 0 2 12c0 1.6.4 3.1 1 4.5z" fill="#FBBC05"/><path d="M12 6c1.5 0 2.8.5 3.8 1.5l2.9-2.9C17 2.9 14.7 2 12 2a10 10 0 0 0-9.1 5.5l3.5 2.6C7.2 7.8 9.4 6 12 6z" fill="#EA4335"/></svg>'
};

export function createBrandLogo(name: BrandName, className = 'brand-logo'): HTMLSpanElement {
  const wrapper = createElement('span', { className });
  wrapper.innerHTML = markup[name];
  return wrapper;
}
