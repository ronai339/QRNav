// static/vite.config.js
import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  build: {
    outDir: 'static/dist',
    rollupOptions: {
      input: "./static/src/main.js"
    }
  }
})
