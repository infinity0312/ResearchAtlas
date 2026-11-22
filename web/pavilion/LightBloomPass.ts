import {Vector2} from 'three';
import {ShaderPass} from 'three/addons/postprocessing/ShaderPass.js';
/** Bounded highlight diffusion. Never mixes a bright full-frame layer over the scene. */
export class LightBloomPass extends ShaderPass{
 constructor(){super({uniforms:{tDiffuse:{value:null},resolution:{value:new Vector2(1,1)},strength:{value:.12},threshold:{value:1.6}},vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,fragmentShader:`uniform sampler2D tDiffuse;uniform vec2 resolution;uniform float strength;uniform float threshold;varying vec2 vUv;
 vec3 highlight(vec2 uv){vec3 c=texture2D(tDiffuse,uv).rgb;float l=dot(c,vec3(.2126,.7152,.0722));return c*smoothstep(threshold,threshold+.7,l);}
 void main(){vec4 base=texture2D(tDiffuse,vUv);vec2 d=2.0/resolution;vec3 glow=vec3(0.);for(int x=-1;x<=1;x++){for(int y=-1;y<=1;y++){glow+=highlight(vUv+vec2(float(x),float(y))*d);}}gl_FragColor=vec4(base.rgb+min(glow/9.0*strength,vec3(.18)),base.a);}`})}
 setSize(width:number,height:number){this.uniforms.resolution.value.set(width,height)}
}
