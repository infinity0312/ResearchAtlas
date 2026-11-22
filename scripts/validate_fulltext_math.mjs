// Parse exactly as the reader does; malformed fences can swallow later prose.
import fs from 'node:fs';
import {unified} from 'unified';
import remarkParse from 'remark-parse';
import remarkMath from 'remark-math';
import katex from 'katex';
const input=fs.readFileSync(process.argv[2],'utf8');
const analysis=process.argv.includes('--analysis')?JSON.parse(input):null;
const fields=analysis?(()=>{const r=analysis.result||analysis;return [['fulltext_markdown',r.fulltext_markdown||''],['summary',r.summary||''],...(r.methods||[]).map((v,i)=>['methods.'+i,v]),...(r.problems||[]).map((v,i)=>['problems.'+i,v]),...(r.claims||[]).map((v,i)=>['claims.'+i+'.text',v.text])];})():[['markdown',input]];
let total=0;const failures=[];
for(const [field,text] of fields){
const normalized=text.split(/(```[\s\S]*?```|`[^`]*`)/g).map((s,i)=>i%2?s:s.replace(/^[ \t]*\$\$([^\n]+?)\$\$[ \t]*$/gm,(_m,v)=>'\n$$\n'+v+'\n$$\n').replace(/\\\[([\s\S]*?)\\\]/g,(_m,v)=>'\n$$\n'+v+'\n$$\n').replace(/\\\(([\s\S]*?)\\\)/g,(_m,v)=>'$'+v+'$')).join('');
const tree=unified().use(remarkParse).use(remarkMath).parse(normalized);
let count=0;const errors=[];
function visit(n){
 if(n.type==='text'&&/(?:\\(?:frac|sum|hat|mathbb|sigma|in|times)\b|[_^]\{[^}]+\}|\b\w+_[a-zA-Z]+\b)/.test(n.value))errors.push({line:n.position?.start.line,error:'疑似裸数学语法：'+n.value.slice(0,160)});
 if(n.type==='math'||n.type==='inlineMath'){
  count++;
  try{katex.renderToString(n.value,{throwOnError:true,displayMode:n.type==='math'});}
  catch(e){errors.push({line:n.position?.start.line,error:String(e.message).slice(0,200)});}
 }
 for(const c of n.children||[])visit(c);
}
visit(tree);
total+=count;failures.push(...errors.map(e=>({field,...e})));
}
console.log(JSON.stringify({formulas:total,errors:failures}));
if(failures.length)process.exitCode=1;
