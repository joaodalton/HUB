import { createElement } from '../../dom';
import type { PlantRow } from '../../services/plantService';
import type { RateioQualificacao } from '../../services/rateioService';
import { createFunilStat, formatNumber } from './shared';
import { t } from '../../services/i18nService';

type Props = {
  plant: PlantRow;
  qualificacao: RateioQualificacao | null;
  loading: boolean;
  showingQualified: boolean;
  selectedUcIds: ReadonlySet<number>;
  onBack: () => void;
  onContinue: () => void;
  onToggleList: () => void;
  onToggleUc: (ucId: number, selected: boolean) => void;
};

export function renderRateioQualificationStage(props: Props): HTMLElement {
  const { plant, qualificacao, loading, showingQualified, selectedUcIds, onBack, onContinue, onToggleList, onToggleUc } = props;
  const wrapper = createElement('section', { className: 'content-stack' });
  const panel = createElement('section', { className: 'data-panel rateio-qualificacao-panel' });
  const title = createElement('div', { className: 'panel-title' });
  const titleText = createElement('div');
  const diaEmissaoUsina = qualificacao?.diaEmissaoUsina ?? plant.diaEmissaoUsina;
  titleText.append(
    createElement('span', { className: 'eyebrow', textContent: plant.nome }),
    createElement('h2', { textContent: t('rateio.qualification.title') }),
    createElement('span', {
      className: 'settings-hint',
      textContent: diaEmissaoUsina != null ? `${t('rateio.qualification.diaEmissaoPrefix')} ${diaEmissaoUsina}` : t('rateio.qualification.diaEmissaoMissing')
    })
  );
  title.appendChild(titleText); panel.appendChild(title);

  if (loading || !qualificacao) {
    panel.appendChild(createElement('p', { className: 'settings-hint', textContent: t('rateio.qualification.calculating') }));
  } else {
    const funnel = createElement('div', { className: 'rateio-funil-grid' });
    funnel.append(createFunilStat(t('rateio.qualification.totalClientes'), qualificacao.totalClientes), createFunilStat(t('rateio.qualification.qualificados'), qualificacao.qualificados));
    panel.appendChild(funnel);
    panel.appendChild(renderRules());
    const show = createElement('button', {
      className: showingQualified ? 'secondary-button' : 'small-button',
      textContent: showingQualified ? t('rateio.qualification.hide') : `${t('rateio.qualification.showPrefix')} (${qualificacao.qualificados})`, type: 'button'
    });
    show.addEventListener('click', onToggleList); panel.appendChild(show);
    if (showingQualified) panel.appendChild(renderQualifiedList(qualificacao, selectedUcIds, onToggleUc));
  }

  const actions = createElement('div', { className: 'form-actions' });
  const back = createElement('button', { className: 'secondary-button', textContent: t('rateio.qualification.back'), type: 'button' });
  const next = createElement('button', { textContent: t('rateio.qualification.continue'), type: 'button' });
  back.addEventListener('click', onBack); next.addEventListener('click', onContinue);
  actions.append(back, next); wrapper.append(panel, actions);
  return wrapper;
}

function renderRules(): HTMLElement {
  const rules = createElement('div', { className: 'rateio-regras' });
  rules.appendChild(createElement('span', { className: 'settings-subheading', textContent: t('rateio.qualification.rulesHeading') }));
  const list = createElement('ul', { className: 'rateio-regras-list' });
  list.appendChild(createElement('li', { textContent: t('rateio.qualification.ruleLeitura') }));
  rules.appendChild(list);
  return rules;
}

function renderQualifiedList(data: RateioQualificacao, selectedUcIds: ReadonlySet<number>, onToggleUc: Props['onToggleUc']): HTMLElement {
  const list = createElement('div', { className: 'rateio-qualificados-list' });
  const qualified = data.ucs.filter((uc) => uc.qualificado);
  if (!qualified.length) {
    list.appendChild(createElement('p', { className: 'empty-state small', textContent: t('rateio.qualification.emptyQualified') }));
    return list;
  }
  const header = createElement('div', { className: 'rateio-qualificado-row rateio-qualificado-header' });
  [
    t('rateio.qualification.columnCliente'),
    t('rateio.qualification.columnApelido'),
    t('rateio.qualification.columnConsumo'),
    t('rateio.qualification.columnDiaEmissao'),
    t('rateio.qualification.columnPercentualSugerido'),
    ''
  ].forEach((label) => header.appendChild(createElement('span', { textContent: label })));
  list.appendChild(header);
  qualified.forEach((uc) => {
    const row = createElement('div', { className: 'rateio-qualificado-row' });
    const name = createElement('div', { className: 'rateio-qualificado-nome' });
    name.append(createElement('strong', { textContent: uc.clienteNome ?? uc.ucCodigo }), createElement('span', { textContent: uc.ucCodigo }));
    const checkbox = createElement('input');
    checkbox.type = 'checkbox'; checkbox.checked = selectedUcIds.has(uc.ucId);
    checkbox.addEventListener('change', () => onToggleUc(uc.ucId, checkbox.checked));
    row.append(
      name,
      createElement('span', { className: 'rateio-distribuicao-texto', textContent: uc.apelido || '-' }),
      createElement('span', { textContent: uc.consumo != null ? `${formatNumber(uc.consumo)} kWh` : '-' }),
      createElement('span', { textContent: uc.diaEmissaoFatura != null ? String(uc.diaEmissaoFatura) : '-' }),
      createElement('span', { textContent: `${formatNumber(uc.percentualSugerido)}%` }),
      checkbox
    );
    list.appendChild(row);
  });
  return list;
}
