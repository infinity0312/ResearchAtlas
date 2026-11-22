import * as THREE from 'three';
// Stationary helical field, x is strictly monotone. RK4 integrates upstream
// from the exact publication-date endpoint; no time-axis deformation.
export function vortexVelocity(p:THREE.Vector3){const r2=p.y*p.y+p.z*p.z,omega=1.8/(1+r2/32),a=0;return new THREE.Vector3(1,-a*p.y-omega*p.z,omega*p.y-a*p.z)}
function step(p:THREE.Vector3,h:number){const a=vortexVelocity(p),b=vortexVelocity(p.clone().addScaledVector(a,h/2)),c=vortexVelocity(p.clone().addScaledVector(b,h/2)),d=vortexVelocity(p.clone().addScaledVector(c,h));return p.clone().addScaledVector(a,h/6).addScaledVector(b,h/3).addScaledVector(c,h/3).addScaledVector(d,h/6)}
export function vortexStrand(endpoint:THREE.Vector3,color:string,width=.048,envelope?:(x:number)=>number){
 const length=Math.max(.28,Math.min(.65,endpoint.x+12.5)),steps=128,path=[endpoint.clone()];let p=endpoint.clone();for(let i=0;i<steps;i++){p=step(p,-length/steps);path.push(p)}path.reverse();if(envelope){const base=envelope(endpoint.x);for(const point of path){const scale=envelope(point.x)/base;point.y*=scale;point.z*=scale}}
 const curve=new THREE.CatmullRomCurve3(path.map(p=>p.sub(endpoint))),segments=160,sides=12,geometry=new THREE.TubeGeometry(curve,segments,width,sides,false),positions=geometry.attributes.position,colors=new Float32Array(positions.count*3),base=new THREE.Color(color),pale=new THREE.Color(color).lerp(new THREE.Color('#d3e5e0'),.25);
 for(let i=0;i<=segments;i++){const u=i/segments,center=curve.getPointAt(u),taper=.12+.88*Math.pow(Math.sin(Math.PI*u),.38),shade=pale.clone().lerp(base,.65+.35*Math.pow(u,.6));for(let j=0;j<=sides;j++){const k=i*(sides+1)+j,v=new THREE.Vector3().fromBufferAttribute(positions,k).sub(center).multiplyScalar(taper).add(center);positions.setXYZ(k,v.x,v.y,v.z);colors.set([shade.r,shade.g,shade.b],k*3)}}geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));return geometry;
}
