export interface DialSection {
 zh:string;
 en?:string;
 href?:string;
 big:number|string;
 unit?:string;
 here?:boolean;
 alert?:boolean;
}

export function drawDial(svg:SVGSVGElement,options:{
 sections:DialSection[];
 gauges?:{label:string;share:number}[];
 idle?:{label:string;big:number|string;unit?:string;sub?:string};
}):void;
