import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        id: '/',
        name: 'Bako',
        short_name: 'Bako',
        description: 'Keep your money together',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#B8F22E',
        background_color: '#F2F2F0',
        categories: ['finance', 'productivity'],
        icons: [
          {
            src: '/bako-launcher-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/bako-launcher-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/bako-launcher-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        globPatterns: ['**/*.{html,js,css,woff2,png,svg,ico}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkOnly',
            method: 'GET',
          },
        ],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
})
