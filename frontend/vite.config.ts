import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
const backend=process.env.PREPCREW_API_ORIGIN||'http://127.0.0.1:8000';
export default defineConfig({plugins:[react(),tailwindcss()],server:{port:Number(process.env.PREPCREW_WEB_PORT||5173),strictPort:true,proxy:{'/api':backend,'/ws':{target:backend.replace(/^http/,'ws'),ws:true}}}});
