import {lazy,Suspense,useRef,useState} from 'react';
import SourceNote from '../ui/SourceNote';
import type {Evidence} from './projectApi';
const PdfReader=lazy(()=>import('../PdfReader'));
export default function ProjectEvidenceSource({evidence:e,onClose}:{evidence:Evidence;onClose:()=>void}){
 const [reading,setReading]=useState(false),[request,setRequest]=useState(0);const root=useRef<HTMLDivElement>(null);
 function readOriginal(){const anchor=root.current?.closest('article')?.querySelector('h4');const top=anchor?.getBoundingClientRect().top;setReading(true);setRequest(v=>v+1);requestAnimationFrame(()=>{if(anchor&&typeof top==='number')window.scrollBy({top:anchor.getBoundingClientRect().top-top,behavior:'instant'})})}
 const source={key:e.id,paperId:e.paper_id,paperTitle:e.snapshot.paper_title,version:e.snapshot.paper_version,analysisId:e.analysis_id,page:e.snapshot.page,text:e.snapshot.claim_text,quote:e.snapshot.quote};
 return <div ref={root} className={'project-source-expanded '+(reading?'has-pdf':'')} data-bound-paper={e.paper_id} data-bound-version={e.snapshot.paper_version} onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onClose()}}}><SourceNote source={source} onClose={onClose} heading="绑定依据与原页" readOriginalLabel="在此核查绑定 PDF" onReadOriginal={readOriginal} onLocate={reading?()=>setRequest(v=>v+1):undefined} originalVisible={reading}>{reading&&<div className="project-source-pdf"><p>仅加载论文 v{e.snapshot.paper_version} · 定位第 {e.snapshot.page} 页；不会回退到最新版本。</p><Suspense fallback={<p role="status">正在准备绑定版本阅读器…</p>}><PdfReader url={`/api/paper/pdf?id=${encodeURIComponent(e.paper_id)}&version=${e.snapshot.paper_version}`} initialPage={e.snapshot.page} navigationRequest={request} layoutKey={e.id} active={reading}/></Suspense></div>}</SourceNote></div>
}
