import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {readFileSync,readdirSync} from 'node:fs';
// Ship PDF resources locally, with the same locked version as the reader.
const pdfAssets=()=>{
 const assets=new Map<string,Buffer>();
 for(const dir of ['cmaps','standard_fonts','wasm'])for(const file of readdirSync(`node_modules/pdfjs-dist/${dir}`))assets.set(`pdfjs/${dir}/${file}`,readFileSync(`node_modules/pdfjs-dist/${dir}/${file}`));
 return {name:'local-pdf-assets',generateBundle(){for(const [fileName,source] of assets)this.emitFile({type:'asset' as const,fileName,source})},configureServer(server){server.middlewares.use((req,res,next)=>{const data=assets.get((req.url||'').split('?')[0].slice(1));if(!data)return next();if(req.url?.endsWith('.wasm'))res.setHeader('Content-Type','application/wasm');res.end(data)})}};
};
export default defineConfig({plugins:[react(),pdfAssets()],server:{proxy:{'/api':'http://127.0.0.1:8765'}},build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom'],charts:['echarts']}}}}});
