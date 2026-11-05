import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 개발 중 브라우저는 http://localhost:5173 만 본다.
// /api/* 로 온 요청을 Vite 가 백엔드(8000)로 대신 보내 주므로(프록시) 브라우저 입장에선 같은 출처 → 쿠키가 그냥 붙는다.
// 운영에서 프론트와 백엔드 도메인이 다르면 그때는 백엔드의 CORS 설정(cors_origins)이 필요하다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
