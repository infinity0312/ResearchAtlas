# Research Atlas

当前架构版本：**0.3.1**，结构版本 **5**。本轮需求收敛、草稿恢复与证据修订见 [0.3.1需求审查](docs/requirements-audit.md)。新增“研发项目”：工况与决策标准、逐主张正反证据、版本评审、冻结交付与内部验证结果回写。当前为本机单组织试点，尚无企业登录、租户隔离和计费。见 [商业化架构](docs/commercial-architecture.md)、[商业化策略与90天验证](docs/commercialization-strategy.md)。现有证据绑定、版本留存和调用预算继续复用。早期架构与恢复说明见 [0.2架构升级](docs/architecture-upgrade.md)、[存储升级](docs/storage-upgrade.md) 和 [界面架构](docs/architecture-ui.md)。历史验证与已知边界是对应时点记录，当前实现以升级文档和代码为准。

文献研究与研发决策工作台。安装位置：`F:\Projects\ResearchAtlas`。应用、Python 虚拟环境、前端依赖和文献数据库均在项目目录。Python 基础运行时使用本机已有 `F:\dev\miniconda3`。

## 启动与停止

双击 `Start Research Atlas.cmd`，打开 http://127.0.0.1:8765 。双击 `Stop Research Atlas.cmd` 停止服务，保留数据。后台进程以隐藏窗口运行；只绑定本机，不向局域网开放，也没有设置开机自启。自动采集仅在后台程序运行时执行，电脑休眠/关机时不执行。

## 首次使用

研发项目试点可直接打开 [研发项目](http://127.0.0.1:8765/#page=projects)：选择场景，填写工况与标准，从已有文库绑定逐条证据，记录验证结果和复核，再导出冻结的MD/JSON。来源未核验或已经变化时，服务端会阻止交付。这个流程不调用模型。完整验收步骤和运行边界见 [0.3交付验证](docs/commercial-verification.md)。

1. 打开“设置与连接”，填写 DeepSeek API Key 和账户当前可用的模型名称，保存并测试连接。在“后台任务”查看测试结果。
2. 在设置中编辑研究领域或添加新领域。支持任意学科，默认的分子材料、生命科学、机器学习只是预设。每个领域维护独立的 arXiv 规则、分类和综述来源。
3. 点击“同步最新文献”。自动同步默认每天一次；机器学习预设默认手动，以免一开始引入过多文献。
4. 导入综述 PDF，选择“提取分类”，核对带页码的证据，再发布分类。发布后，名称和定义都用于论文分类，旧分类与分析保留。
5. 打开论文，选择“全文分析”。也可以在设置中启用“同步后自动分析”，并设置每日任务上限。该上限按任务数量计算，不等于金额/token 上限；长论文会多次调用模型。

## 当前可用能力

- LaTeX 数学渲染、持久标签词库与按标签过滤的文献关系图。使用方法和支持边界见 `docs/math-and-graph.md`。
- 图谱提供明暗画布、邻居聚焦、智能标签、专注视图；布局由 Web Worker 中的 d3-force 计算。视觉优化与验证见 `docs/graph-visual-refresh.md`。

- 持久化文献、跨领域去重、版本留存、收藏与检索。
- arXiv API 增量采集；API 不可用时官方 RSS 降级，保留明确的覆盖范围提示。
- DeepSeek JSON 接口、输出 schema 检查、原文引文定位、失败重试和任务记录。
- 文本型 PDF 分页解析；大文档分段分析，不静默截断。
- 综述分类草稿、定义与证据、分类发布及历史版本。
- 趋势、分类分布、方法×方向矩阵；点击方向可查看论文。
- 桌面与窄屏布局、搜索、收藏、证据阅读、任务与设置页面。
- API 与 worker 独立进程；任务持久化；单 worker 文件锁；任务去重；概览随数据版本失效的缓存；图表按需加载。

## 已知边界（2026-09-26）

- 本机历史查询 API 返回 HTTP 406，官方 RSS 可用。已采集 18 篇真实公告（分子材料 10、生命科学 8）。这不是完整的近 30 天数据。RSS 的日期是公告日期，不冒充首次发表日期；不把未覆盖的日期画成零论文。历史 API 恢复后，可重新同步补全。
- DeepSeek 已配置，真实模型列表和聊天连接通过；联调使用公开 arXiv 论文与综述，具体结果见 docs/live-validation.json。自动化测试使用隔离夹具，不混入正式文献库。少量真实样本不代表全面准确率评估。
- 首版采用 SQLite WAL + 持久化单 worker 队列，适合个人单机；未部署 PostgreSQL、pgvector、Celery/RabbitMQ。迁移时要替换 JSON 过滤适配、队列实现和迁移脚本，并重新做并发测试。
- PDF 解析为 pypdf 轻量实现，不是 Docling/OCR；扫描件、复杂表格、图片与公式理解不保证。解析失败会显示错误，不发布“全文已读”。接口预留解析器替换。
- 证据校验是“原文片段存在性检查”，不能证明模型的语义理解正确；局限分作者声明、实验观察、待验证推断。长文按段阅读后进行全文综合，筛选最多 15 条核心结论并保留原始证据；语义准确性仍需核验。综述提取保留草稿，由用户审核发布。
- 尚未接入 embedding、语义检索、Zotero、PubMed/bioRxiv、团队权限、周报。关键词搜索目前为 SQLite 查询；这些扩展不需要改变领域模型。
- 领域图目前为分类卡片与方法矩阵，尚无主题降维散点图或引用网络。
- “重新分析”在内容、分类、模型及提示词版本不变时复用结果，避免重复计费。失败任务重试还会复用成功的分段；缓存随提示词、模型和输入变化自动失效。

## 扩展边界

`backend/contracts.py`：SourceAdapter / ParserAdapter / ModelAdapter 协议及结构化输出 schema。

`backend/db.py`：Domain 与 Taxonomy 独立于学科；Paper 和 Version 以来源 ID/版本存储；Membership 支持一篇论文属于多个领域；Analysis 保存领域、分类版本、原文 hash、模型及提示词版本。

`backend/sources.py`：arXiv API 与 RSS。`backend/parser.py`：隔离 PDF 解析。`backend/analysis.py`：模型与证据。`backend/worker.py`：持久任务执行、自动采集。`backend/app.py`：短查询与操作接口。`web/`：用户界面。

新增学科只需添加领域配置。新增非 arXiv 来源时应增加来源命名空间/标识映射与适配器，不让不同来源 ID 发生冲突。更换队列或数据库需通过仓储边界迁移，而不是假定设置一个环境变量就完成迁移。

## 数据与密钥

数据在 `data/atlas.db`、`data/uploads/`、`data/documents/`。Windows 密钥使用 DPAPI，绑定当前 Windows 用户；不要将密钥文件拷贝给别的用户。API Key 不回传前端，不进入源码。Linux 分支仅提供权限为 0600 的文件，未在该平台验收。

只允许本机 Host；写接口校验客户端标识及同源 Origin。PDF 上传最多 25MB，解析子进程超时 90 秒，最多 150 页；没有容器级内存沙箱，不应作为不受信任的公共上传服务。

备份前先停止应用，将整个 data 目录复制到独立备份位置。SQLite WAL 活跃时不要仅复制 atlas.db。恢复需同一 Windows 用户才能解密 provider.key；否则重新输入 API Key。

## 开发与验证

最新更新：摘要阅读排版、按需证据卡、教材式数学讲解、领域分类树与 Markdown 笔记系列，见 [reading-notes-hierarchy.md](docs/reading-notes-hierarchy.md)。整篇解析文本已封装至后台，原始公式请通过内置 PDF 阅读器核对。

论文阅读支持公式渲染、旧分析上下标兼容、内置 PDF 翻页缩放和本地相关文献推荐；图谱支持平滑聚焦与缩放。实现与测试说明见 [reading-motion-related.md](docs/reading-motion-related.md)。PDF.js 使用 Apache-2.0 许可证，本地资源随构建打包。

```powershell
npm ci
npm run build
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
npm run test:e2e
.\.venv\Scripts\python.exe -m tests.benchmark
```

首次跑浏览器测试需 `npx playwright install chromium`。测试使用隔离数据库和明确标注的夹具，不写正式文献库，不调用真实 DeepSeek。浏览器测试服务端口 8770；生产应用端口 8765。Playwright 的浏览器测试运行时由工具保存在默认用户缓存，不属于应用运行依赖。

结果见 `docs/benchmark.json`、`docs/browser-tests.json`、`docs/verification.md`。软件测试不能替代真实论文分析准确性的人工评估。

主要开源组件及许可证：React/TypeScript/Vite/FastAPI（MIT），SQLAlchemy（MIT），pypdf（BSD-3-Clause），ECharts（Apache-2.0），TanStack Query（MIT），Lucide（ISC）。发布时按锁定版本保留各依赖的许可证。DeepSeek 是外部 API 服务。


## 统一论文探索

首页「论文探索」可统一选择检索、抓取、分析和统计。全范围元数据进入独立目录，按月质量初筛后仅精选论文进入精读库；重复任务复用检查点，达到每日全文分析上限后等待下一个额度周期。配置、评分依据与数据源说明见 [工作流说明](docs/exploration-workflow.md)。
