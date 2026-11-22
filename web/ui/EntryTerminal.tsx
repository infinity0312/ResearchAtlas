import {useProximityLight} from './useProximityLight';
import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {api} from '../api';
import {useAppearance} from './Appearance';
const loadApp=()=>import('../App');
const App=lazy(loadApp);
const sessionKey='atlas.terminal.entered';
function seen(){try{return sessionStorage.getItem(sessionKey)==='1'}catch{return false}}

/** Startup is a read-only warmup. The workspace stays mounted during a replay. */
export default function EntryTerminal(){
 useProximityLight();
 const {appearance,reduced}=useAppearance(),client=useQueryClient();
 const [active,setActive]=useState(()=>appearance.edition==='prism'&&!seen());
 const [run,setRun]=useState(0),[leaving,setLeaving]=useState(false);
 const [steps,setSteps]=useState(['等待','等待','等待']);
 const closeRef=useRef<HTMLButtonElement>(null),restore=useRef<HTMLElement|null>(null);
 function finish(){setLeaving(true)}
 useEffect(()=>{const replay=()=>{restore.current=document.activeElement as HTMLElement;setLeaving(false);setActive(true);setRun(n=>n+1)};window.addEventListener('atlas:replay-entry',replay);return()=>window.removeEventListener('atlas:replay-entry',replay)},[]);
 useEffect(()=>{
  if(!active)return;
  let live=true;const controller=new AbortController();const timers:ReturnType<typeof setTimeout>[]=[];
  setSteps(['加载中','加载中','加载中']);closeRef.current?.focus();
  const began=performance.now();
  const timeout=<T,>(p:Promise<T>)=>Promise.race([p,new Promise<never>((_,reject)=>timers.push(setTimeout(()=>reject(new Error('timeout')),6000)))]);
  const tasks=[loadApp(),document.fonts.ready,client.fetchQuery({queryKey:['domains'],queryFn:()=>api('/domains',{signal:controller.signal}),staleTime:15000,retry:false})];
  Promise.allSettled(tasks.map((task,i)=>timeout(task).then(()=>{if(live)setSteps(s=>s.map((v,j)=>i===j?'就绪':v))},()=>{if(live)setSteps(s=>s.map((v,j)=>i===j?'稍后重试':v))}))).then(()=>{
   if(live)timers.push(setTimeout(()=>setLeaving(true),Math.max(0,(reduced?0:2400)-(performance.now()-began))));
  });
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();finish()}if(e.key==='Tab'){e.preventDefault();closeRef.current?.focus()}};
  window.addEventListener('keydown',key);
  return()=>{live=false;controller.abort();timers.forEach(clearTimeout);window.removeEventListener('keydown',key)};
 },[active,run,client,reduced]);
 useEffect(()=>{if(!leaving)return;const t=setTimeout(()=>{setActive(false);setLeaving(false);try{sessionStorage.setItem(sessionKey,'1')}catch{}},reduced?0:540);return()=>clearTimeout(t)},[leaving,reduced]);
 useEffect(()=>{if(active||!restore.current)return;const t=setTimeout(()=>{const target=restore.current;restore.current=null;if(target?.isConnected)target.focus({preventScroll:true})},50);return()=>clearTimeout(t)},[active]);
 const done=steps.filter(s=>s!=='等待'&&s!=='加载中').length;
 return <><div inert={active} aria-hidden={active||undefined} className={active?'terminal-workspace entering':'terminal-workspace'}><Suspense fallback={<div className="loading" role="status">正在加载研究工作台…</div>}><App/></Suspense></div>{active&&<section className={'terminal-entry'+(leaving?' is-leaving':'')} role="dialog" aria-modal="true" aria-label="研究终端启动">
 <header><span>RA / RESEARCH ATLAS</span><button ref={closeRef} onClick={finish}>跳过动画 <kbd>ESC</kbd></button></header>
 <div className="entry-composition" aria-hidden="true"><div className="entry-reticle"/><svg viewBox="0 0 600 400"><path className="entry-rule" d="M0 200H600M300 0V400"/><g className="entry-mark"><path d="M202 286L300 112L398 286M251 200H349M231 250H369"/><circle cx="300" cy="200" r="132"/><path d="M151 200H172M428 200H449M300 51V72M300 328V349"/></g></svg><span className="entry-coordinate">KNOWLEDGE / CONNECTED</span></div>
 <div className="entry-title"><span>个人研究工作台</span><h1>RESEARCH<br/><strong>ATLAS</strong></h1><p>文献 · 证据 · 洞见</p></div>
 <footer><div className="entry-progress" role="progressbar" aria-label="资源预载" aria-valuemin={0} aria-valuemax={3} aria-valuenow={done}><i style={{transform:`scaleX(${done/3})`}}/></div><div className="entry-steps" role="status">{['界面资源','阅读字体','领域索引'].map((label,i)=><div key={label}><small>0{i+1}</small><span>{label}</span><b>{steps[i]}</b></div>)}</div><p>资源预载完成后进入工作台 <span>{done} / 3</span></p></footer>
 </section>}</>;
}
