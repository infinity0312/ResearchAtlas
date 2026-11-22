import * as THREE from 'three';

/** Screen-space ink ribbons: real 3D centerlines, no cylindrical highlights.
 * Pick geometry remains separate so the hairline is still easy to select. */
export function filamentGeometry(curve:THREE.Curve<THREE.Vector3>,segments=96){
 const positions:number[]=[],tangents:number[]=[],uvs:number[]=[],indices:number[]=[];
 for(let i=0;i<=segments;i++){
  const u=i/segments,p=curve.getPointAt(u),t=curve.getTangentAt(u);
  for(const side of [-1,1]){positions.push(...p.toArray());tangents.push(...t.toArray());uvs.push(u,side)}
  if(i<segments){const a=i*2;indices.push(a,a+1,a+2,a+1,a+3,a+2)}
 }
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.setAttribute('tangent',new THREE.Float32BufferAttribute(tangents,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));g.setIndex(indices);g.computeBoundingSphere();return g;
}

export function filamentMaterial(color:string,viewport:THREE.Vector2,time:{value:number}){
 return new THREE.ShaderMaterial({
  uniforms:{ink:{value:new THREE.Color(color)},viewport:{value:viewport},time,focus:{value:0}},
  transparent:true,depthWrite:false,depthTest:true,side:THREE.DoubleSide,toneMapped:false,
  vertexShader:`
   attribute vec3 tangent; uniform vec2 viewport; uniform float focus;
   varying vec2 vRibbon;
   void main(){
    vec4 p=projectionMatrix*modelViewMatrix*vec4(position,1.);
    vec4 q=projectionMatrix*modelViewMatrix*vec4(position+tangent*.01,1.);
    vec2 d=(q.xy/q.w-p.xy/p.w)*viewport;
    vec2 normal=vec2(-d.y,d.x)/max(length(d),.00001);
    float taper=.22+.78*pow(sin(3.14159265*uv.x),.35);
    float halfWidth=(1.1+.25*focus)*taper;
    p.xy+=normal*uv.y*halfWidth*2./viewport*p.w;
    gl_Position=p; vRibbon=uv;
   }`,
  fragmentShader:`
   uniform vec3 ink; uniform float time; uniform float focus; varying vec2 vRibbon;
   void main(){
    float aa=max(fwidth(vRibbon.y),.12);
    float coverage=1.-smoothstep(1.-aa,1.,abs(vRibbon.y));
    float ends=smoothstep(0.,.035,vRibbon.x)*(1.-smoothstep(.965,1.,vRibbon.x));
    float flow=.5+.5*sin(vRibbon.x*6.283-time*.65);
    vec3 c=mix(ink,vec3(.12,.30,.25),focus*.28);
    gl_FragColor=vec4(c,coverage*ends*(.77+.08*flow+.12*focus));
    #include <colorspace_fragment>
   }`
 });
}
