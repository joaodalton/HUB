import { createDataTable } from '../components/DataTable';
import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getEmpresas, type EmpresaRow } from '../services/empresaService';

export function createEmpresasPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const layout = createBaseLayout({ content, eyebrow: 'Plataforma', title: 'Empresas' });
  const loading = useGlobalLoading();

  void load();
  return layout;

  async function load(): Promise<void> {
    loading.show();
    try {
      const empresas = await getEmpresas();
      content.replaceChildren(createDataTable<EmpresaRow>({
        title: 'Empresas cadastradas',
        eyebrow: 'Listagem',
        rows: empresas,
        emptyMessage: 'Nenhuma empresa cadastrada ainda.',
        columns: [
          { key: 'nome', label: 'Nome' },
          { key: 'slug', label: 'Slug' },
          { key: 'status', label: 'Status' },
          { key: 'totalUsuarios', label: 'Usuários', align: 'right' },
          { key: 'cnpj', label: 'CNPJ', render: (row) => row.cnpj || '-' }
        ]
      }));
    } catch {
      content.replaceChildren(createElement('p', {
        className: 'empty-state', textContent: 'Não foi possível carregar as empresas.'
      }));
    } finally {
      loading.hide();
    }
  }
}
