import type { Translation } from '../services/i18nService';

export const authDict: Record<string, Translation> = {
  'auth.login.heading': { pt: 'Bem-vindo ao HUB', en: 'Welcome to HUB', fr: 'Bienvenue sur HUB' },
  'auth.login.subheading': { pt: 'Faça login para continuar', en: 'Log in to continue', fr: 'Connectez-vous pour continuer' },
  'auth.login.emailLabel': { pt: 'E-mail', en: 'Email', fr: 'E-mail' },
  'auth.login.senhaLabel': { pt: 'Senha', en: 'Password', fr: 'Mot de passe' },
  'auth.login.rememberMe': { pt: 'Lembrar meu acesso', en: 'Remember me', fr: 'Se souvenir de moi' },
  'auth.login.submit': { pt: 'Entrar no HUB', en: 'Log in to HUB', fr: 'Se connecter à HUB' },
  'auth.login.genericError': { pt: 'Não foi possível entrar.', en: 'Could not log in.', fr: "Impossible de se connecter." },
  'auth.login.forgotPassword': { pt: 'Esqueci minha senha', en: 'Forgot my password', fr: 'Mot de passe oublié' },
  'auth.login.showPassword': { pt: 'Mostrar senha', en: 'Show password', fr: 'Afficher le mot de passe' },
  'auth.login.hidePassword': { pt: 'Ocultar senha', en: 'Hide password', fr: 'Masquer le mot de passe' },
  'auth.login.subtitle': { pt: 'Sistema de Gestão', en: 'Management System', fr: 'Système de gestion' },
  'auth.login.tagline': { pt: 'Conectando usinas, unidades e pessoas.', en: 'Connecting plants, units and people.', fr: 'Connecter centrales, unités et personnes.' },
  'auth.login.checkingServer': { pt: 'Verificando servidor...', en: 'Checking server...', fr: 'Vérification du serveur...' },
  'auth.login.serverOnline': { pt: 'Servidor Online', en: 'Server Online', fr: 'Serveur en ligne' },
  'auth.login.serverOffline': { pt: 'Servidor Offline', en: 'Server Offline', fr: 'Serveur hors ligne' },
  'auth.login.emailPlaceholder': { pt: 'usuario@email.com', en: 'user@email.com', fr: 'utilisateur@email.com' }
};
