import {memo,useEffect,useRef} from 'react';
import 'katex/dist/katex.min.css';
import './math-layout.css';
import {legacyMath} from './legacyMath';

/** React owns the wrapper, KaTeX exclusively owns its text subtree. */
export default memo(function MathText({text,className='',legacy=false}:{text:string;className?:string;legacy?:boolean}){
 const ref=useRef<HTMLSpanElement>(null);
 useEffect(()=>{const node=ref.current!;node.textContent=legacy?legacyMath(text):text;let cancelled=false;
 import('katex/contrib/auto-render').then(({default:renderMathInElement})=>{if(cancelled)return;
  renderMathInElement(node,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'\\(',right:'\\)',display:false},{left:'$',right:'$',display:false},...['equation','equation*','align','align*','gather','gather*'].map(e=>({left:`\\begin{${e}}`,right:`\\end{${e}}`,display:true}))],throwOnError:false,trust:false,strict:'ignore',maxExpand:500,maxSize:20,output:'htmlAndMathml',errorCallback:()=>{}});
 }).catch(()=>{if(!cancelled)node.textContent=text});return()=>{cancelled=true};},[text,legacy]);
 return <span ref={ref} className={'math-text '+className}/>;
});
