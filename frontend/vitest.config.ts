import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

const dependencies = fileURLToPath(new URL('./node_modules/', import.meta.url))

export default defineConfig({
  root: '..',
  resolve: {
    alias: {
      react: `${dependencies}react`,
      'react-router-dom': `${dependencies}react-router-dom`,
      '@testing-library/react': `${dependencies}@testing-library/react/dist/index.js`,
    },
  },
  plugins: [react()],
  test: { environment: 'jsdom', setupFiles: ['frontend/vitest.setup.ts'], include: ['tests/frontend/**/*.test.tsx'], clearMocks: true },
})
