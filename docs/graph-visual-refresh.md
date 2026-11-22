# 图谱视觉与交互优化

参考 Obsidian 的图谱交互，以及开源 Quartz 和 Force Graph 的局部聚焦、节点层次与力导向设计。本次不复制 Obsidian 或 Quartz 源码；实现采用独立 SVG 渲染器和 d3-force（ISC 许可证）。已有 ECharts 保留给统计图表。

- [Obsidian 图谱说明](https://obsidian.md/help/plugins/graph)
- [Quartz 图谱设计与配置](https://quartz.jzhao.xyz/features/graph-view)
- [Quartz v4 图谱源码](https://github.com/jackyzha0/quartz/blob/v4/quartz/components/scripts/graph.inline.ts)
- [Force Graph](https://github.com/vasturiano/force-graph)
- [D3 force simulation](https://d3js.org/d3-force/simulation)

## 已实现

深色、浅色画布；更小的节点与细连线；节点大小随连接数变化；标签类型配色；悬停突出邻居，点击标签保持聚焦；长名称详情卡；标签碰撞避让和随缩放调整可见性；智能、更多、仅聚焦三种标签显示方式。可平移、拖动节点、缩放、适应画布、重置、收起筛选栏和进入专注视图。键盘可以聚焦节点并打开论文，Escape 退出专注视图。

单篇论文采用展开的环形布局，多文献用带碰撞约束的力导向布局。计算在 Web Worker 内完成并限制为 220 次迭代；切换数据时终止旧任务。加载完成后不持续运行物理模拟。不改动数据库、文献内容或标签关系，也不调用 LLM。

## 验证

生产构建成功；9 项浏览器测试全部通过，包括原有标签管理、公式、阅读与手机布局，以及新增的密集图布局、聚焦、缩放、主题、专注视图、筛选栏、键盘阅读。

隔离的 120 篇测试文献、24 个标签、360 条边：点击选择到图谱可用 1099ms，包含模拟查询、懒加载和布局，不是生产大规模性能结论。原始结果：graph-render-benchmark.json。graph-polish-fixture.png 是明确标注的测试数据截图，不混入正式库。

正式库目前只有一篇文献完成全文分析，所以真实图呈一篇论文连接多个标签的形态；未为了视觉效果制造论文或关系。
