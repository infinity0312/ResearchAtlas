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

const legacySwatches:Record<string,string>={
 '#327c72':industrialSeries[0],
 '#7e964b':'#6a718c',
};

export function editionSwatch(color:string,edition:Appearance['edition']){
 return edition==='industrial'?legacySwatches[color.toLowerCase()]??color:color;
}

export function useEditionSwatch(){
 const {appearance}=useAppearance();
 return (color:string)=>editionSwatch(color,appearance.edition);
}
