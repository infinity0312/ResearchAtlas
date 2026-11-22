import {useId,type ReactNode} from 'react';
import {ExternalLink,X,LocateFixed} from 'lucide-react';
import MathText from '../MathText';
import {useAppearance} from './Appearance';
import './source-note.css';

export type SourceRecord={key?:string;paperId:string;paperTitle:string;version:number;analysisId?:number;page:number;text:string;quote:string};
type Props={source:SourceRecord;onClose?:()=>void;closeLabel?:string;heading?:string;onReadOriginal?:()=>void;readOriginalLabel?:string;onLocate?:()=>void;originalVisible?:boolean;available?:boolean;children?:ReactNode};

/** A source identity is shared by the selected passage and its adjacent context.
 * This component never fetches or substitutes a newer analysis or PDF. */
export default function SourceNote({source,onClose,closeLabel='关闭来源',heading='来源与原页',onReadOriginal,readOriginalLabel='在 PDF 中查看此页',onLocate,originalVisible=false,available=true,children}:Props){
 const titleId=useId();
 const {appearance}=useAppearance();
 const page=Math.max(1,source.page||1);
 const pdf='/api/paper/pdf?id='+encodeURIComponent(source.paperId)+'&version='+encodeURIComponent(source.version)+'#page='+page;
 return <section className="linked-source-note" aria-labelledby={titleId} data-source-key={source.key||`${source.paperId}:${source.version}:${source.analysisId||''}:${page}`}>
  <header className="linked-source-heading"><div><span className="linked-source-kicker">{heading}</span><h3 id={titleId}><MathText text={source.paperTitle}/></h3></div>{onClose&&<button type="button" className="icon-button linked-source-close" aria-label={closeLabel} onClick={onClose}><X size={18}/></button>}</header>
  <div className="linked-source-coordinate"><span key={page} className={appearance.edition==='industrial'?'ef-marker':undefined}>论文 v{source.version} · 第 {page} 页</span>{source.analysisId!==undefined&&<span>分析 #{source.analysisId}</span>}</div>
  {available?<div className="linked-source-actions">{onReadOriginal&&!originalVisible&&<button type="button" className="button primary small" onClick={onReadOriginal}>{readOriginalLabel}</button>}{onLocate&&originalVisible&&<button type="button" className="button small" onClick={onLocate}><LocateFixed size={14}/>定位引用页</button>}<a className="text-button" href={pdf} target="_blank" rel="noreferrer">新窗口查看原页 <ExternalLink size={13}/></a></div>:<p className="linked-source-missing">此绑定版本的本地 PDF 不可用，主张与引文仍保留。</p>}
  <p className="linked-source-claim"><MathText text={source.text} legacy/></p>
  <blockquote className="linked-source-quote"><MathText text={source.quote}/></blockquote>
  <details className="linked-source-precision"><summary>来源定位说明</summary><p>依据记录按页定位，尚未执行逐句匹配。原页与此条依据使用此处显示的版本。</p></details>
  {children}
 </section>;
}
