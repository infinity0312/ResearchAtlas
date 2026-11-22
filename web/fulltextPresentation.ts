// Reader-facing cleanup also applies to existing records; raw provenance stays archived.
export function fulltextForReading(markdown:string){
 const lines=markdown.split(/\r?\n/);let excludedLevel=0;
 const body=lines.filter(line=>{
  const heading=line.match(/^(#{1,6})\s+(.+)$/);
  if(heading){
   if(excludedLevel&&heading[1].length<=excludedLevel)excludedLevel=0;
   if(/^(?:\d+[.、 ]*)?(?:审阅报告|审阅说明|核查过程|审核记录|审计记录|模型自评|验收记录|阅读范围|核查范围)\s*$/.test(heading[2])){excludedLevel=heading[1].length;return false}
  }
  return !excludedLevel;
 }).join('\n');
 const text=body.replace(/^(\s*#{1,6}\s+)(?:GPT[-‑–]?6[-‑–]?Sol|Codex)\s*[·：:]?\s*全文(?:重析|研读|分析|审阅)\s*[·：:—–-]?\s*/i,'$1');
 const start=text.search(/^##\s/m);
 const intro=start<0?'':text.slice(0,start).split(/\r?\n\s*\r?\n/).filter(paragraph=>
  !/^\s*#\s/.test(paragraph)&&!/核查范围|阅读范围|证据范围|核读\s*PDF|本地\s*(?:PDF|解析)|解析(?:文本|源|快照).*?(?:SHA|哈希)|SHA-?256|已逐页阅读/.test(paragraph)).join('\n\n');
 const cleaned=(start<0?text:intro+'\n\n'+text.slice(start)).replace(/^(?:[ \t]*)(?:本次(?:审阅|审核|核查|验收)|模型自评|审核结论|验收结论|审阅说明)[：:][^\n]*$/gm,'');
 return cleaned.replace(/\n{3,}/g,'\n\n').trim();
}
