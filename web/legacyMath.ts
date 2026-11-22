// Display-only compatibility for old model output; never modifies stored evidence.
const greek:Record<string,string>={'ρ':'\\rho','α':'\\alpha','β':'\\beta','γ':'\\gamma','δ':'\\delta','Δ':'\\Delta','θ':'\\theta','λ':'\\lambda','μ':'\\mu','σ':'\\sigma','ϕ':'\\phi','φ':'\\phi','ψ':'\\psi','ω':'\\omega'};
function bareEquations(part:string){
 return part.replace(/([ρσθλμαβγδω])(?:_?([a-zA-Z][a-zA-Z0-9]*))?\s*=\s*(min|max|exp|log|sqrt)\(([^()\n]{1,120})\)/g,(_m,base,sub,fn,args)=>{
  if(!/^[\d\s.,+*/^−\-ρσθλμαβγδωa-zA-Z_{}]+$/.test(args))return _m;
  const texArgs=args.replace(/[ρσθλμαβγδω]/g,(c:string)=>(greek[c]||c)+' ').replace(/−/g,'-');
  return `\\(${greek[base]}${sub?`_{${sub.length>1?`\\mathrm{${sub}}`:sub}}`:''} = \\${fn}${fn==='sqrt'?`{${texArgs}}`:`(${texArgs})`}\\)`;
 });
}
export function legacyMath(text:string){
 text=bareEquationsOutsideMath(text);
 const protectedParts=/(\$\$[\s\S]*?\$\$|\$(?:\\.|[^$\n])*?\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\}|```[\s\S]*?```|`[^`]*`|https?:\/\/\S+)/g;
 return text.split(protectedParts).map((part,i)=>i%2?part:part.replace(/(?<![\w\\])(?:ρ|rho)_?(init|env)\s*\(r\)/g,(_m,sub)=>`\\(\\rho_{\\mathrm{${sub}}}(\\mathbf{r})\\)`).replace(/(?<![\w\\])([A-Za-zραβγδΔθλμσϕφψω])(?:_([a-zA-Z0-9]+)|\^(\d+))(?![\w])/g,(_match,base,sub,power)=>`\\(${greek[base]||base}${sub?`_{${/^[a-zA-Z]{2,}$/.test(sub)?`\\mathrm{${sub}}`:sub}}`:`^{${power}}`}\\)`)).join('');
}

function bareEquationsOutsideMath(text:string){
 return text.split(/(\$\$[\s\S]*?\$\$|\$(?:\\.|[^$\n])*?\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\}|```[\s\S]*?```|`[^`]*`|https?:\/\/\S+)/g).map((part,i)=>i%2?part:bareEquations(part)).join('');
}
