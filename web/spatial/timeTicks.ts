// Calendar-aligned UTC ticks; density depends on projected screen length.
export function timeTicks(min:number,max:number,pixels:number){
 if(!Number.isFinite(min)||!Number.isFinite(max))return [];
 if(max<=min)return [{x:0,text:new Date(min).toISOString().slice(0,10)}];
 const span=max-min,day=86400000,target=span/Math.max(1,pixels/105);
 const steps=[1,2,5,10,20,50,100];
 let unit:'day'|'month'|'year',step:number;
 if(target>day*365){unit='year';step=steps.find(n=>n*365.2425*day>=target)||100}
 else if(target>day*28){unit='month';step=[1,2,3,6,12].find(n=>n*30.44*day>=target)||12}
 else{unit='day';step=[1,2,7,14,28].find(n=>n*day>=target)||28}
 const date=new Date(min);date.setUTCHours(0,0,0,0);
 if(unit==='year'){date.setUTCMonth(0,1);date.setUTCFullYear(Math.ceil(date.getUTCFullYear()/step)*step)}
 if(unit==='month'){date.setUTCDate(1);date.setUTCMonth(Math.ceil(date.getUTCMonth()/step)*step)}
 const advance=()=>{if(unit==='year')date.setUTCFullYear(date.getUTCFullYear()+step);else if(unit==='month')date.setUTCMonth(date.getUTCMonth()+step);else date.setUTCDate(date.getUTCDate()+step)};
 while(date.getTime()<min)advance();
 const ticks=[];while(date.getTime()<=max&&ticks.length<500){ticks.push({x:(date.getTime()-min)/span*22-11,text:date.toISOString().slice(0,unit==='year'?4:unit==='month'?7:10)});advance()}
 return ticks;
}
