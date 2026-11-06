import { describe, it, expect } from 'vitest';
import { createLogsPanel } from '../pages/settingsLogs';
import type { LogRow } from '../services/logsService';

const baseLog: LogRow = {
  id: 1,
  nivel: 'info',
  acao: 'create',
  entidade: 'Documento',
  entidadeId: 1,
  mensagem: 'Documento "Fatura.pdf" enviado',
  metadados: { id: 42, segredo: 'nao deveria aparecer' },
  criadoEm: '2026-01-01T10:00:00'
};

describe('settingsLogs drawer', () => {
  it('abre o drawer com a mensagem, sem expor o JSON de metadados', () => {
    const panel = createLogsPanel([baseLog], true);
    document.body.appendChild(panel);

    const row = panel.querySelector('tbody tr') as HTMLTableRowElement;
    row.click();

    const drawer = document.querySelector('.detail-drawer-overlay') as HTMLElement;
    expect(drawer).not.toBeNull();
    expect(drawer.textContent).toContain(baseLog.mensagem);
    expect(drawer.textContent).not.toContain('segredo');
    expect(drawer.querySelector('pre')).toBeNull();

    drawer.remove();
    panel.remove();
  });

  it('destaca a mensagem como erro quando o nivel e error', () => {
    const errorLog: LogRow = { ...baseLog, id: 2, nivel: 'error', acao: 'email_failed', mensagem: 'Falha ao enviar e-mail para cliente@exemplo.com' };
    const panel = createLogsPanel([errorLog], true);
    document.body.appendChild(panel);

    const row = panel.querySelector('tbody tr') as HTMLTableRowElement;
    row.click();

    const drawer = document.querySelector('.detail-drawer-overlay') as HTMLElement;
    const message = drawer.querySelector('.log-drawer-message-error');
    expect(message?.textContent).toBe(errorLog.mensagem);

    drawer.remove();
    panel.remove();
  });

  it('nao mostra mais a coluna tecnica de acao na tabela', () => {
    const panel = createLogsPanel([baseLog], true);
    const headers = Array.from(panel.querySelectorAll('thead th')).map((th) => th.textContent);
    expect(headers).toEqual(['Data/Hora', 'Nível', 'Mensagem']);
  });
});
