import {memo} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './math-layout.css';

// Transform text nodes only: wiki links inside code or formulas remain literal.
function wikiLinks(){return (tree:any)=>{function visit(node:any){if(!node.children||['link','code','inlineCode','math','inlineMath'].includes(node.type))return;node.children=node.children.flatMap((child:any)=>{if(child.type!=='text'){visit(child);return [child]}const out:any[]=[];let end=0;const value=child.value as string;for(const match of value.matchAll(/\[\[([^\]\n]+)\]\]/g)){out.push({type:'text',value:value.slice(end,match.index)});const [name,label]=match[1].split('|');out.push({type:'link',url:'#note='+encodeURIComponent(name.trim()),children:[{type:'text',value:label||name}]});end=match.index!+match[0].length}out.push({type:'text',value:value.slice(end)});return out})}visit(tree)}}
export default memo(function Markdown({text,onWiki}:{text:string;onWiki?:(name:string)=>void}){
 const normalized=text.split(/(```[\s\S]*?```|`[^`]*`)/g).map((s,i)=>i%2?s:s.replace(/^[ \t]*\$\$([^\n]+?)\$\$[ \t]*$/gm,(_m,v)=>'\n$$\n'+v+'\n$$\n').replace(/\\\[([\s\S]*?)\\\]/g,(_m,v)=>'\n$$\n'+v+'\n$$\n').replace(/\\\(([\s\S]*?)\\\)/g,(_m,v)=>'$'+v+'$')).join('');
 return <div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm,remarkMath,wikiLinks]} rehypePlugins={[[rehypeKatex,{throwOnError:false,trust:false,strict:'ignore',maxExpand:500}]]} skipHtml components={{a:({href,children})=>href?.startsWith('#note=')?<button className="wiki-link" onClick={()=>onWiki?.(decodeURIComponent(href.slice(6)))}>{children}</button>:<a href={href} target="_blank" rel="noreferrer">{children}</a>}}>{normalized}</ReactMarkdown></div>
});
