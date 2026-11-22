import {createContext,useContext,useEffect,useLayoutEffect,useState,type ReactNode} from 'react';
export type Appearance={edition:'classic'|'prism'|'industrial';motion:'system'|'reduced';effects:'auto'|'off';density:'comfortable'|'compact';quality:'auto'|'high'|'balanced'};
export const appearanceKey='atlas.appearance.v1';
export const defaultAppearance:Appearance={edition:'industrial',motion:'system',effects:'auto',density:'comfortable',quality:'auto'};
export function validateAppearance(value:unknown):Appearance{const v=(value&&typeof value==='object'?value:{}) as Partial<Appearance>;return {edition:'industrial',motion:v.motion==='reduced'?'reduced':'system',effects:v.effects==='off'?'off':'auto',density:v.density==='compact'?'compact':'comfortable',quality:v.quality==='high'?'high':v.quality==='balanced'?'balanced':'auto'}}
function read(){try{return validateAppearance(JSON.parse(localStorage.getItem(appearanceKey)||'null'))}catch{return defaultAppearance}}
const Context=createContext<{appearance:Appearance;update:(patch:Partial<Appearance>)=>void;reduced:boolean;storageAvailable:boolean}>({appearance:defaultAppearance,update:()=>{},reduced:false,storageAvailable:true});
export function AppearanceProvider({children}:{children:ReactNode}){
 const [appearance,setAppearance]=useState(read),[systemReduced,setSystemReduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches),[storageAvailable,setStorageAvailable]=useState(true);
 useEffect(()=>{const media=matchMedia('(prefers-reduced-motion: reduce)');const changed=()=>setSystemReduced(media.matches);media.addEventListener('change',changed);const storage=(e:StorageEvent)=>{if(e.key===appearanceKey||e.key===null)setAppearance(read())};window.addEventListener('storage',storage);return()=>{media.removeEventListener('change',changed);window.removeEventListener('storage',storage)}},[]);
 const reduced=appearance.motion==='reduced'||systemReduced;
 useLayoutEffect(()=>{const root=document.documentElement;root.dataset.edition=appearance.edition;root.dataset.motion=reduced?'reduced':'full';root.dataset.density=appearance.density;root.dataset.effects=appearance.effects},[appearance,reduced]);
 function update(patch:Partial<Appearance>){const next=validateAppearance({...appearance,...patch});setAppearance(next);try{localStorage.setItem(appearanceKey,JSON.stringify(next));setStorageAvailable(true)}catch{setStorageAvailable(false)}}
 return <Context.Provider value={{appearance,update,reduced,storageAvailable}}>{children}</Context.Provider>
}
export const useAppearance=()=>useContext(Context);
