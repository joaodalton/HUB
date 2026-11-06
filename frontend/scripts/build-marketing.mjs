import { execSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const frontendDir = fileURLToPath(new URL('..', import.meta.url));
const landingSrc = fileURLToPath(new URL('../../landing/index.html', import.meta.url));
const landingDest = fileURLToPath(new URL('../dist-marketing/index.html', import.meta.url));

execSync('npx vite build --config vite.marketing.config.ts', { cwd: frontendDir, stdio: 'inherit' });

// shortcut: fallback é um placeholder, precisa configurar VITE_APP_URL em produção
const appUrl = process.env.VITE_APP_URL || 'https://app.hub.com.br';
const landingHtml = await readFile(landingSrc, 'utf8');
await writeFile(landingDest, landingHtml.replaceAll('[URL_DO_APP]', appUrl), 'utf8');

console.log(`landing copiada para dist-marketing/index.html (VITE_APP_URL=${appUrl})`);
