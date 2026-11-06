import { resolve } from 'path';
import { defineConfig } from 'vite';

// Build só checkout + cadastro-empresa (sem main) pro site estático de marketing.
// Config própria (não deriva de vite.config.ts): mergeConfig mescla chaves de
// rollupOptions.input por objeto em vez de substituir, o que manteria o
// entry "main" indesejado no build.
export default defineConfig({
  build: {
    outDir: 'dist-marketing',
    rollupOptions: {
      input: {
        checkout: resolve(__dirname, 'checkout.html'),
        cadastroEmpresa: resolve(__dirname, 'cadastro-empresa.html')
      }
    }
  }
});
