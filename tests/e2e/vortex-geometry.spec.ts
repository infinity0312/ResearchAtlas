import {test,expect} from '@playwright/test';
import * as THREE from 'three';
import {vortexStrand,vortexVelocity} from '../../web/spatial/vortexGeometry';
test('integrated strand preserves publication endpoint and finite monotone geometry',()=>{const end=new THREE.Vector3(8,2,1),g=vortexStrand(end,'#397d72'),p=g.attributes.position;let previous=-Infinity;for(let i=0;i<=160;i++){const center=new THREE.Vector3();for(let j=0;j<12;j++)center.add(new THREE.Vector3().fromBufferAttribute(p,i*13+j));center.divideScalar(12);expect(center.x).toBeGreaterThanOrEqual(previous-1e-5);previous=center.x;for(const v of center.toArray())expect(Number.isFinite(v)).toBe(true);if(i===160)expect(center.length()).toBeLessThan(1e-5)}expect(vortexVelocity(end).x).toBe(1);g.dispose()});

import {temporalBundleRadii} from '../../web/spatial/temporalDensity';
test('dense periods widen the bundle envelope without varying stroke thickness',()=>{const widths=temporalBundleRadii([0,...Array.from({length:20},(_,i)=>10*365*86400000+i*86400000)]);expect(widths[0]).toBeLessThan(widths[10]);expect(widths.every(w=>w>=1.15&&w<=3.6)).toBe(true);expect(temporalBundleRadii([])).toEqual([])});
