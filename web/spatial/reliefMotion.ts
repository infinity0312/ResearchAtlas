// Adapted to the matrix from RhineLabUI/src/motion.ts: travelling packet + analytic damping.
export const smooth=(t:number)=>{t=Math.max(0,Math.min(1,t));return t*t*t*(10+t*(-15+6*t))};
export function packet(distance:number,age:number){if(age<0||age>3.4)return 0;const front=distance-age*5.5;return .34*smooth(age/.16)*Math.exp(-age*.9)*Math.cos(front*.95)*Math.exp(-.5*(front/1.7)**2)}
export function drift(x:number,y:number,t:number){return .045*Math.sin(t*.78+x*.32-y*.4)+.018*Math.sin(t*.48-x*.22+y*.25)}
export function damp(value:number,velocity:number,target:number,dt:number){const rate=11,delta=value-target,impulse=velocity+rate*delta,decay=Math.exp(-rate*dt);return {value:target+(delta+impulse*dt)*decay,velocity:(velocity-rate*impulse*dt)*decay}}
