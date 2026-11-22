# 前端模块边界与接口契约

此文档对应架构升级后的前端。后端分析质量由 `backend/evidence_contracts.py` 和 `backend/analysis_repository.py` 产生，模型预算由 `backend/model_runtime.py` 管理。

## 查询与交互职责

| 模块 | 职责 | 查询与更新 |
|---|---|---|
| `web/App.tsx` | 工作台导航、领域选择、论文列表、打开阅读器和全局提示 | 持续读取 `jobs` 供导航计数；任务身份/状态指纹变化时刷新研究数据 |
| `web/app/JobsPage.tsx` | 任务记录、暂停/恢复、重试、整理及删除记录 | 与 App 共用 `['jobs']` 查询；控制状态使用 `['job-control']`；操作后只直接失效 `jobs`、`job-control` 和 `exploration-latest` |
| `web/PaperDetail.tsx` | 单篇阅读、分析、PDF、提问与协作标签页 | `['detail', paperId, domainId]`，保持领域分析的查询身份 |
| `web/AnalysisQuality.tsx` | 展示服务端质量状态 | 无请求、无状态推断；列表模式提供简短标记和完整可访问名称，阅读模式使用原生 `details/summary` |
| `web/app/ModelBudgetSettings.tsx` | 调用预算编辑和用量统计 | `['model-budget']` 读取预算；`['model-usage']` 每 15 秒读取用量；显式保存预算后更新预算缓存并失效用量统计 |

App 与 JobsPage 的 `jobs` 查询键保持相同，TanStack Query 共享缓存。后台任务的完成状态和论文内容的质量状态分别展示，任务完成不推导为语义核验通过。

预算表单加载只执行 GET。未成功加载预算时不创建表单，不提交默认值。表单有修改才允许保存；正在编辑时不使用自动重新获取的值覆盖输入。其他模块调用旧的 App `act()` 仍会全局失效查询，这是现有页面控制器后续拆分的边界，本轮提取的任务和预算控制器使用独立更新路径。

## 分析质量契约

论文列表和详情的规范入口分别是 `paper.analysis.quality` 和 `detail.analysis.quality`。组件不读取 `analysis.result.quality`，不根据模型名称、引文数量或已完成任务推导质量。

```ts
type AnalysisQuality = {
  contract_version: 1;
  provenance: 'evidence_pipeline' | 'legacy';
  evidence: 'verified' | 'partial' | 'unverified';
  grounding: 'bound' | 'legacy';
  semantic: 'not_reviewed' | 'model_reviewed' | 'human_reviewed';
  freshness: 'current' | 'stale';
  rejected_evidence: number;
};
```

- `evidence` 表示引文校验范围。通过原文片段校验并不代表论断在语义上成立。
- `grounding: bound` 表示展示结论引用了通过校验的依据 ID；引用关系也不等于科学结论被证实。
- `semantic` 独立表达复核状态。目前后端规范读取路径默认 `not_reviewed`；生成模型的自述不能升级这个状态。将来引入复核流程时，应使用可信的审阅记录更新读取契约。
- `freshness: stale` 可由论文版本、分类版本或解析来源修订触发。前端显示“结果待更新”，不将过期原因限定为 PDF 版本变化。
- 历史分析在后端读取时得到保守的 `legacy / unverified / legacy / not_reviewed`，不回写历史证据快照。旧服务没有 `quality` 或契约版本不受支持时，前端不显示虚构的核验状态。

## 模型预算和用量契约

`GET /api/model-usage/budget` 返回 `daily_tokens`、`task_tokens`、`task_calls` 及只读的 `timezone: 'Asia/Shanghai'`。三种上限为正整数或 `null`。`PUT` 不携带 timezone；省略字段保留原值，显式 `null` 取消该上限。预算编辑器将用户确认后的三个字段显式提交，留空转换为 `null`。

`GET /api/model-usage` 的 `budget` 包含三个上限，不包含 timezone；响应顶层提供 `day`、`timezone`、`totals`、分组和最近请求。UI 使用以下统计：

| 字段 | 展示意义 |
|---|---|
| `totals.known_tokens` | 服务商已报告并通过格式校验的 Token 总量 |
| `totals.reserved_tokens` | 正在请求或用量未知请求继续保留的保守估计额度 |
| `totals.attempts` | 已记录的真实请求尝试数量 |
| `totals.unknown_calls` | 传输或服务商用量无法确认的请求数量 |

预留量不展示为实际消费或费用。用量未知时显示原因提示：配置每日 Token 上限会暂停当天后续模型请求；配置任务 Token 上限会暂停相关任务的后续调用。每日计数按北京时间零点切换，和旧的每日分析任务数量限制分别管理。日期标签使用响应的 `day`，读取失败时保留带日期的最后一份统计并显示错误，可手动刷新。

## 验证

`tests/e2e/analysis-quality.spec.ts` 覆盖历史、部分核验、过期、缺失契约、规范状态优先于嵌入数据以及列表到阅读器的导航。

`tests/e2e/model-budget.spec.ts` 覆盖加载无写入、显式保存、保留 null 上限、保存后用量刷新、手动刷新、预留量与已报告量区分和接口失败时不提交默认值。

现有后台任务、阅读/PDF、全文公式以及多尺寸布局用例继续验证拆分前后的用户流程。E2E 使用 `tests/serve.py` 的临时数据库；路由夹具不会调用真实模型。
