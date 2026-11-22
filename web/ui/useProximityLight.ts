import {useEffect} from 'react';
import {useAppearance} from './Appearance';
/** One GPU surface, shared by nearby cards and charts; no permanent render loop. */
export function useProximityLight(){
 const {appearance,reduced}=useAppearance();
 useEffect(()=>{
  if(appearance.edition!=='prism'||appearance.effects==='off'||reduced||!matchMedia('(pointer:fine)').matches)return;
  const canvas=document.createElement('canvas');canvas.className='proximity-light';canvas.setAttribute('aria-hidden','true');document.body.append(canvas);
  const gl=canvas.getContext('webgl',{alpha:true,premultipliedAlpha:false,antialias:false,powerPreference:'low-power'});
  if(!gl){canvas.remove();return}
  const shaders:WebGLShader[]=[];
  const shader=(type:number,source:string)=>{const s=gl.createShader(type)!;shaders.push(s);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error('shader');return s};
  let program:WebGLProgram;
  try{program=gl.createProgram()!;gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec2 p;varying vec2 uv;void main(){uv=p*.5+.5;gl_Position=vec4(p,0.,1.);}'));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`precision mediump float;varying vec2 uv;uniform vec2 light;uniform float strength;uniform float aspect;
  void main(){vec2 q=vec2(uv.x,1.-uv.y);vec3 pos=vec3((q-.5)*vec2(aspect,1.),0.);vec3 l=normalize(vec3((light-.5)*vec2(aspect,1.),.45)-pos);vec3 eye=normalize(vec3(0.,0.,1.4)-pos);vec3 h=normalize(l+eye);float spec=pow(max(h.z,0.),40.);float edge=smoothstep(0.,.035,min(min(q.x,1.-q.x),min(q.y,1.-q.y)));gl_FragColor=vec4(.82,1.,.77,spec*.22*strength*edge);}`));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('link')}catch{shaders.forEach(s=>gl.deleteShader(s));canvas.remove();return}
  gl.useProgram(program);const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);const loc=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
  const light=gl.getUniformLocation(program,'light'),strength=gl.getUniformLocation(program,'strength'),aspect=gl.getUniformLocation(program,'aspect');
  let target:HTMLElement|null=null,frame=0,x=-9999,y=-9999,px=.5,py=.5,alpha=0,down=false,last=0,dead=false;
  const reset=()=>{target?.style.removeProperty('transform');target?.style.removeProperty('will-change');target?.removeAttribute('data-proximity');target=null};
  const draw=(now:number)=>{frame=0;if(dead)return;const dt=Math.min(40,now-(last||now-16));last=now;let rect=target?.getBoundingClientRect();let near=rect?Math.max(rect.left-x,0,x-rect.right,rect.top-y,0,y-rect.bottom):999;
   const desired=target?.isConnected&&!down&&near<90?1:0,b=1-Math.exp(-dt/90);alpha+=(desired-alpha)*b;
   if(rect&&target){const tx=Math.max(0,Math.min(1,(x-rect.left)/rect.width)),ty=Math.max(0,Math.min(1,(y-rect.top)/rect.height));px+=(tx-px)*b;py+=(ty-py)*b;
    // Keep canvas coordinate systems flat while chart tooltips and brushing are active.
    const chart=target.matches('.chart,.macro-chart,.paper-view-chart');target.style.transform=chart?`translateY(${-alpha*1.5}px)`:`perspective(1000px) rotateX(${( .5-py)*alpha*2.4}deg) rotateY(${(px-.5)*alpha*2.4}deg) translateY(${-alpha*2}px)`;
    canvas.style.cssText=`left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px;opacity:${alpha};`;
    const w=Math.max(1,Math.round(rect.width)),h=Math.max(1,Math.round(rect.height));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h)}
    gl.uniform2f(light,px,py);gl.uniform1f(strength,alpha);gl.uniform1f(aspect,w/h);gl.drawArrays(gl.TRIANGLES,0,6);canvas.dataset.renderer='webgl-specular';
   }
   if(!desired&&alpha<.005){reset();canvas.style.opacity='0';last=0;return}
   const targetX=rect?Math.max(0,Math.min(1,(x-rect.left)/rect.width)):.5;
   const targetY=rect?Math.max(0,Math.min(1,(y-rect.top)/rect.height)):.5;
   if(Math.abs(desired-alpha)>.005||Math.abs(px-targetX)>.003||Math.abs(py-targetY)>.003)frame=requestAnimationFrame(draw);
  };
  const wake=()=>{if(!frame&&!dead)frame=requestAnimationFrame(draw)};
  const move=(e:PointerEvent)=>{if(e.pointerType!=='mouse')return;x=e.clientX;y=e.clientY;if(down)return;let best:HTMLElement|null=null,distance=90;
   if(!(e.target as Element).closest('.overlay,.modal,.terminal-entry'))for(const el of document.querySelectorAll<HTMLElement>('.metric,.chart,.macro-chart,.paper-view-chart:not(.relief-host)')){const r=el.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight)continue;const d=Math.hypot(Math.max(r.left-x,0,x-r.right),Math.max(r.top-y,0,y-r.bottom));if(d<distance){best=el;distance=d}}
   if(best!==target){reset();target=best;alpha=0;if(target){target.style.willChange='transform';target.dataset.proximity='active'}}wake();
  };
  const leave=()=>{x=y=-9999;wake()},press=()=>{down=true;leave()},release=()=>{down=false};
  const lost=(e:Event)=>{e.preventDefault();dead=true;cancelAnimationFrame(frame);reset();canvas.remove()};
  document.addEventListener('pointermove',move,{passive:true});document.addEventListener('pointerdown',press);document.addEventListener('pointerup',release);document.addEventListener('pointercancel',release);document.addEventListener('pointerleave',leave);window.addEventListener('blur',leave);window.addEventListener('scroll',leave,true);canvas.addEventListener('webglcontextlost',lost);
  return()=>{dead=true;cancelAnimationFrame(frame);reset();document.removeEventListener('pointermove',move);document.removeEventListener('pointerdown',press);document.removeEventListener('pointerup',release);document.removeEventListener('pointercancel',release);document.removeEventListener('pointerleave',leave);window.removeEventListener('blur',leave);window.removeEventListener('scroll',leave,true);canvas.removeEventListener('webglcontextlost',lost);gl.deleteBuffer(buffer);shaders.forEach(s=>gl.deleteShader(s));gl.deleteProgram(program);gl.getExtension('WEBGL_lose_context')?.loseContext();canvas.remove()};
 },[appearance.edition,appearance.effects,reduced]);
}
