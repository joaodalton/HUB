import { createElement } from '../dom';
import { useGlobalLoading } from '../hooks/useGlobalLoading';
import { useToast } from '../hooks/useToast';
import { createBaseLayout } from '../layouts/BaseLayout';
import { getCurrentUser } from '../services/authService';
import { getClients, type ClientRow } from '../services/clientsService';
import {
  createWhatsappConversation, getWhatsappConversations, getWhatsappMessages, sendWhatsappText,
  type WhatsappConversation, type WhatsappMessage,
} from '../services/whatsappService';

export function createMessagesPage(): HTMLElement {
  const content = createElement('section', { className: 'content-stack' });
  const toast = useToast();
  const loading = useGlobalLoading();
  let conversations: WhatsappConversation[] = [];
  let clients: ClientRow[] = [];
  let selected: WhatsappConversation | null = null;
  let messages: WhatsappMessage[] = [];
  let loaded = false;
  let creating = false;

  const layout = createBaseLayout({ content, eyebrow: 'Automações', title: 'Mensagens' });
  render();
  void load();
  return layout;

  async function load(): Promise<void> {
    try {
      [conversations, clients] = await Promise.all([getWhatsappConversations(), getClients()]);
      if (selected) selected = conversations.find((item) => item.id === selected?.id) ?? null;
      if (selected) messages = await getWhatsappMessages(selected.id);
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível carregar as mensagens.'); }
    finally { loaded = true; render(); }
  }

  function render(): void {
    const panel = createElement('section', { className: 'whatsapp-layout' });
    panel.append(createConversationList(), createThread());
    content.replaceChildren(panel);
  }

  function createConversationList(): HTMLElement {
    const list = createElement('aside', { className: 'whatsapp-list' });
    const header = createElement('div', { className: 'whatsapp-list-header' });
    header.append(createElement('h2', { textContent: 'Conversas' }));
    if (canSend()) {
      const create = createElement('button', { type: 'button', textContent: creating ? 'Cancelar' : 'Nova conversa' });
      create.addEventListener('click', () => { creating = !creating; render(); });
      header.appendChild(create);
    }
    list.appendChild(header);
    if (creating) list.appendChild(createNewConversationForm());
    if (!loaded) { list.appendChild(createElement('p', { className: 'whatsapp-empty', textContent: 'Carregando...' })); return list; }
    if (!conversations.length) list.appendChild(createElement('p', { className: 'whatsapp-empty', textContent: 'Nenhuma conversa ainda.' }));
    conversations.forEach((conversation) => {
      const button = createElement('button', { className: selected?.id === conversation.id ? 'whatsapp-conversation active' : 'whatsapp-conversation', type: 'button' });
      const head = createElement('span', { className: 'whatsapp-conversation-head' });
      head.append(createElement('strong', { textContent: conversation.contactName || conversation.clientName || conversation.phoneNumber }), createElement('span', { textContent: conversation.unreadCount ? String(conversation.unreadCount) : '' }));
      button.append(head, createElement('span', { className: 'whatsapp-conversation-preview', textContent: conversation.lastMessage?.body || conversation.phoneNumber }));
      button.addEventListener('click', () => void selectConversation(conversation));
      list.appendChild(button);
    });
    return list;
  }

  function createNewConversationForm(): HTMLElement {
    const form = createElement('form', { className: 'whatsapp-new-form' });
    const client = createElement('select');
    const emptyClient = createElement('option', { textContent: 'Selecionar cliente (opcional)' }); emptyClient.value = ''; client.appendChild(emptyClient);
    clients.filter((item) => item.telefone).forEach((item) => { const option = createElement('option', { textContent: `${item.nome} — ${item.telefone}` }); option.value = String(item.id); client.appendChild(option); });
    const phone = createElement('input'); phone.placeholder = 'Telefone com DDI e DDD';
    const name = createElement('input'); name.placeholder = 'Nome do contato';
    const save = createElement('button', { type: 'submit', textContent: 'Abrir conversa' });
    form.append(client, phone, name, save);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      void (async () => {
        loading.show();
        try {
          const conversation = await createWhatsappConversation({ clientId: client.value ? Number(client.value) : undefined, phoneNumber: phone.value, contactName: name.value });
          creating = false; selected = conversation; await load();
        } catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível abrir a conversa.'); }
        finally { loading.hide(); }
      })();
    });
    return form;
  }

  function createThread(): HTMLElement {
    const thread = createElement('section', { className: 'whatsapp-thread' });
    if (!selected) {
      thread.appendChild(createElement('p', { className: 'whatsapp-empty', textContent: 'Selecione ou crie uma conversa para ver o histórico.' }));
      return thread;
    }
    const title = createElement('header', { className: 'whatsapp-thread-header' });
    title.append(createElement('strong', { textContent: selected.contactName || selected.clientName || selected.phoneNumber }), createElement('span', { textContent: selected.phoneNumber }));
    const stream = createElement('div', { className: 'whatsapp-messages' });
    messages.forEach((message) => {
      const bubble = createElement('article', { className: message.direction === 'outbound' ? 'whatsapp-bubble outbound' : 'whatsapp-bubble' });
      bubble.append(createElement('span', { textContent: message.body || '(mensagem sem texto)' }), createElement('small', { className: 'whatsapp-message-meta', textContent: `${message.status} · ${formatDate(message.createdAt)}` }));
      stream.appendChild(bubble);
    });
    thread.append(title, stream);
    if (canSend()) thread.appendChild(createComposer());
    return thread;
  }

  function createComposer(): HTMLElement {
    const form = createElement('form', { className: 'whatsapp-composer' });
    const input = createElement('textarea'); input.placeholder = 'Digite uma mensagem'; input.required = true;
    const send = createElement('button', { type: 'submit', textContent: 'Enviar' });
    form.append(input, send);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!selected) return;
      void (async () => {
        loading.show(); send.disabled = true;
        try { await sendWhatsappText(selected!.id, input.value); input.value = ''; await load(); }
        catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível enviar a mensagem.'); }
        finally { loading.hide(); send.disabled = false; }
      })();
    });
    return form;
  }

  async function selectConversation(conversation: WhatsappConversation): Promise<void> {
    selected = conversation; render();
    try { messages = await getWhatsappMessages(conversation.id); selected = { ...conversation, unreadCount: 0 }; }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Não foi possível carregar o histórico.'); }
    finally { render(); }
  }
}

function canSend(): boolean { return ['owner', 'admin', 'operator'].includes(getCurrentUser()?.role ?? ''); }
function formatDate(value: string | null): string { return value ? new Date(value).toLocaleString('pt-BR') : 'agora'; }
