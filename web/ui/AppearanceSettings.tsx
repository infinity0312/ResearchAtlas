import {useAppearance,type Appearance} from './Appearance';

export default function AppearanceSettings(){
 const {appearance,update,reduced,storageAvailable}=useAppearance();
 return <section className="panel appearance-settings" aria-labelledby="appearance-title">
  <div className="panel-title">
   <div><h2 id="appearance-title">界面与视觉体验</h2><p>Atlas 工业图册 · 动效与密度偏好保存在当前浏览器。</p></div>
   <span className="tag">{storageAvailable?'自动保存':'当前浏览器无法保存偏好'}</span>
  </div>
  <div className="appearance-controls">
   <label>动效偏好<select aria-label="动效偏好" value={appearance.motion} onChange={e=>update({motion:e.target.value as Appearance['motion']})}>
    <option value="system">跟随系统</option><option value="reduced">减少动态效果</option>
   </select><small>{reduced?'当前已减少动态效果':'短暂转场与交互反馈'}</small></label>
   <label>界面密度<select aria-label="界面密度" value={appearance.density} onChange={e=>update({density:e.target.value as Appearance['density']})}>
    <option value="comfortable">舒适</option><option value="compact">紧凑</option>
   </select><small>调整导航与列表间距</small></label>
  </div>
 </section>;
}
