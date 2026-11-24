import {useAppearance,type Appearance} from '../Appearance';

export const industrialChart={
 ink:'#262626',
 muted:'#606060',
 line:'#d6d5d0',
 grid:'#eae9e5',
 paper:'#fdfcfa',
 fill:'#e7e5de',
 accent:'#496983',
};

export const industrialSeries=['#496983','#9d693c','#775889','#995c66','#6b737f','#695b48'];
export const industrialHeatmap=['#faf8f1','#eee7bc','#d6c775','#9a8443','#514723'];

function displayHue(hue:number) {
 const normalized=((hue%360)+360)%360;
 return normalized>=72&&normalized<177?Math.round(200+(normalized-72)*.64):hue;
}

export function editionSwatch(color:string,edition:Appearance['edition']){
 if(edition!=='industrial')return color;
 const value=color.trim();
 const hex=/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value);
 if(hex){
  const digits=hex[1].length===3?[...hex[1]].map(digit=>digit.repeat(2)).join(''):hex[1];
  const r=parseInt(digits.slice(0,2),16),g=parseInt(digits.slice(2,4),16),b=parseInt(digits.slice(4,6),16);
  const range=g-Math.min(r,b);
  if(!range||g<Math.max(r,b))return value;
  const hue=60*(2+(b-r)/range);
  if(displayHue(hue)===hue)return value;
  return hue<112?'#6a718c':industrialSeries[0];
 }
 const hsl=/^(hsl[a]?\(\s*)([-+]?\d+(?:\.\d+)?)(?=deg\b|[\s,])/i.exec(value);
 if(hsl)return hsl[1]+displayHue(Number(hsl[2]))+value.slice(hsl[0].length);
 return industrialSeries[0];
}

export function useEditionSwatch(){
 const {appearance}=useAppearance();
 return (color:string)=>editionSwatch(color,appearance.edition);
}
