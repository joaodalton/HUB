import type { Translation } from '../services/i18nService';

export const sharedDict: Record<string, Translation> = {
  // DataTable.ts
  'shared.dataTable.chooseColumns': { pt: 'Escolher colunas da tabela', en: 'Choose table columns', fr: 'Choisir les colonnes du tableau' },
  'shared.dataTable.columnsModalTitle': { pt: 'Colunas da tabela', en: 'Table columns', fr: 'Colonnes du tableau' },
  'shared.dataTable.dragToReorder': { pt: 'Arrastar para reordenar', en: 'Drag to reorder', fr: 'Faire glisser pour réorganiser' },

  // Modal.ts
  'shared.modal.close': { pt: 'Fechar', en: 'Close', fr: 'Fermer' },

  // DetailDrawer.ts
  'shared.detailDrawer.closeTitle': { pt: 'Fechar', en: 'Close', fr: 'Fermer' },
  'shared.detailDrawer.closeAriaLabel': { pt: 'Fechar painel', en: 'Close panel', fr: 'Fermer le panneau' },

  // ContextHelp.ts
  'shared.contextHelp.ariaLabelPrefix': { pt: 'Ajuda', en: 'Help', fr: 'Aide' },

  // UiState.ts
  'shared.uiState.loadingList': { pt: 'Carregando lista', en: 'Loading list', fr: 'Chargement de la liste' },
  'shared.uiState.loadingTable': { pt: 'Carregando tabela', en: 'Loading table', fr: 'Chargement du tableau' },

  // SearchPanel.ts
  'shared.searchPanel.searchLabel': { pt: 'Buscar', en: 'Search', fr: 'Rechercher' },
  'shared.searchPanel.searchPlaceholder': { pt: 'cliente, termo, imagem ou pasta...', en: 'client, term, image or folder...', fr: 'client, terme, image ou dossier...' },
  'shared.searchPanel.searchButton': { pt: 'Buscar', en: 'Search', fr: 'Rechercher' },
  'shared.searchPanel.hint': { pt: 'Pesquise, escolha os documentos e deixe tudo separado no painel ao lado.', en: 'Search, pick the documents and leave everything set aside in the side panel.', fr: "Recherchez, choisissez les documents et laissez tout prêt dans le panneau latéral." },

  // cadastroFields.ts
  'shared.validation.phoneInvalid': { pt: 'Informe um telefone válido.', en: 'Enter a valid phone number.', fr: 'Saisissez un numéro de téléphone valide.' },
  'shared.validation.phoneFormat': { pt: 'Informe DDD e celular de 9 dígitos ou telefone fixo de 8 dígitos.', en: 'Enter an area code with a 9-digit mobile number or an 8-digit landline number.', fr: "Saisissez l'indicatif régional avec un numéro de mobile à 9 chiffres ou un numéro fixe à 8 chiffres." },
  'shared.validation.cpfInvalid': { pt: 'Informe um CPF válido com 11 dígitos.', en: 'Enter a valid 11-digit CPF.', fr: 'Saisissez un CPF valide à 11 chiffres.' },
  'shared.validation.cnpjInvalid': { pt: 'Informe um CNPJ válido com 14 dígitos.', en: 'Enter a valid 14-digit CNPJ.', fr: 'Saisissez un CNPJ valide à 14 chiffres.' },
  'shared.validation.ucCopelInvalid': { pt: 'UC Copel deve ter 12 ou 15 dígitos.', en: 'Copel unit number must have 12 or 15 digits.', fr: "Le numéro d'unité Copel doit avoir 12 ou 15 chiffres." }
};
