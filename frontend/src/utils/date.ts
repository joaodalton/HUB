// Formatação de data compartilhada (padrão pt-BR dd/mm/aaaa).
export function formatDate(value: string | null | undefined, fallback = '—'): string {
  if (!value) return fallback;
  const [year, month, day] = value.slice(0, 10).split('-');
  return year && month && day ? `${day}/${month}/${year}` : fallback;
}

export function formatDateTime(value: string | null | undefined, fallback = '—'): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  const dia = String(date.getDate()).padStart(2, '0');
  const mes = String(date.getMonth() + 1).padStart(2, '0');
  const hora = date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  return `${dia}/${mes}/${date.getFullYear()} ${hora}`;
}
