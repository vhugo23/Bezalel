import { cpSync, createReadStream, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, normalize, sep } from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
// Excalidraw loads its hand-drawn fonts at runtime. Serve them from the app instead of esm.sh.
const excalidrawFonts=fileURLToPath(new URL('./node_modules/@excalidraw/excalidraw/dist/prod/fonts',import.meta.url));
function excalidrawAssets():Plugin{
  return {name:'excalidraw-assets',
    configureServer(server){server.middlewares.use('/excalidraw/fonts',(req,res,next)=>{
      const file=normalize(join(excalidrawFonts,decodeURIComponent((req.url||'').split('?')[0])));
      if(!file.startsWith(excalidrawFonts+sep)||!existsSync(file)||!statSync(file).isFile())return next();
      res.setHeader('Content-Type',file.endsWith('.woff2')?'font/woff2':'application/octet-stream');res.setHeader('Cache-Control','public, max-age=31536000, immutable');
      createReadStream(file).pipe(res);
    });},
    writeBundle(options){cpSync(excalidrawFonts,join(options.dir||'dist','excalidraw/fonts'),{recursive:true});},
  };
}
const backend=process.env.PREPCREW_API_ORIGIN||'http://127.0.0.1:8000';
export default defineConfig({
  cacheDir:process.env.PREPCREW_WEB_PORT?'../.artifacts/vite-e2e-cache':'node_modules/.vite',
  plugins:[react(),tailwindcss(),excalidrawAssets()],
  // Parakeet imports ORT's base entry, which otherwise omits the WebGPU provider.
  resolve:{alias:[{find:/^onnxruntime-web$/,replacement:'onnxruntime-web/webgpu'}]},
  worker:{format:'es'},
  // Discover worker-only dependencies before serving the page; otherwise Vite
  // reloads the app during the first quota fallback to optimize them.
  optimizeDeps:{include:['kokoro-js','parakeet.js']},
  server:{port:Number(process.env.PREPCREW_WEB_PORT||5173),strictPort:true,proxy:{'/api':backend,'/ws':{target:backend.replace(/^http/,'ws'),ws:true}}},
});
