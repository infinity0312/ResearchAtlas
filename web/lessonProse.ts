/** Older tutorials used inline enumeration. Preserve code/math verbatim. */
export function lessonProse(text:string){
 const tokens:string[]=[];
 let body=text.replace(/```[\s\S]*?```|`[^`]*`|\$\$[\s\S]*?\$\$|\$[^$\n]*\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)/g,s=>{tokens.push(s);return `\uE000${tokens.length-1}\uE001`});
 const markers=[...body.matchAll(/[（(](\d{1,2})[）)]/g)];
 // Only a sequence starting with 1 is prose enumeration, not equation references.
 const prefix=markers.length?body.slice(0,markers[0].index).trim():'';
 if(markers.length>=2&&(!prefix||/[：:]$/.test(prefix))&&markers[0][1]==='1'&&markers.every((m,i)=>Number(m[1])===i+1)){
  body=body.replace(/[（(](\d{1,2})[）)]\s*/g,'\n\n$1. ');
 }
 body=body.replace(/(^|\n)[（(]?(\d{1,2})[）)]\s*/g,'$1$2. ');
 // Long prose gets paragraph breaks at sentence boundaries, never inside math.
 body=body.split(/\n\n/).map(p=>{
  if(/^(?:\s*[-*#>|]|\d+\.\s)/.test(p)||p.includes('\n'))return p;
  let length=0;return p.replace(/[^。！？]*[。！？]|[^。！？]+$/g,s=>{
   length+=s.length;if(length<160)return s;length=0;return s+'\n\n';
  }).trim();
 }).join('\n\n');
 return body.replace(/\uE000(\d+)\uE001/g,(_,i)=>tokens[Number(i)]);
}
