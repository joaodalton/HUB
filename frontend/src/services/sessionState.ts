import type { AuthUser } from './authService';

let cachedUser: AuthUser | null = null;
let sessionChecked = false;

export function getCachedUser(): AuthUser | null {
  return cachedUser;
}

export function setCachedUser(user: AuthUser | null): void {
  cachedUser = user;
  sessionChecked = true;
}

export function isSessionChecked(): boolean {
  return sessionChecked;
}

export function clearSession(): void {
  cachedUser = null;
  sessionChecked = true;
}
