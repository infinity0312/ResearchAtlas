# 数据库版本升级与恢复

数据库仍使用 SQLite。`backend/migrations.py` 将原来的启动时零散 `ALTER TABLE` 改为有版本、名称、校验和与应用时间的 `schema_migrations` 账本。迁移只增加兼容列和索引，不重建论文、分析、笔记或证据记录，也不向旧库追加可能导致现存记录失败的外键约束。

## 升级约定

1. 每次启动的 schema 初始化先获取 `BEGIN IMMEDIATE` 写锁。在一个事务内验证账本、创建缺失表、执行待应用迁移、写入账本。失败时 DDL 与账本一起回滚。
2. 已发布迁移不可改写。增加 schema 时追加连续版本；不要修改已经应用的迁移名称、DDL 或校验和。
3. 旧库没有账本时，版本 1 接纳原有的八个兼容列：已存在列保持原值，缺失列补上原来的默认值。版本 2 添加分析当前版本查询、领域最新分析查询和任务队列索引。版本 3 纳入 `model_usage` 持久化用量账本，并对该表全部必需列进行 schema 完整性检查。
4. 数据库版本比程序新、账本缺版本、校验和不匹配，或已应用迁移对应的列/索引缺失时，启动会失败。应使用匹配的程序版本并调查数据来源，不能删除账本绕过检查。
5. `migration_status(engine)` 只读取 schema 状态，不运行迁移。测试的 `Base.metadata.drop_all` 同时清理非 ORM 账本，避免空数据库沿用旧迁移状态。

新增 ORM 表必须在 `run_migrations` 之前注册到 `Base.metadata`。业务数据的初始化、FTS 搜索初始化在迁移成功之后执行。当前工具负责 SQLite；它不会伪装支持其他数据库。

## 备份

在项目目录执行，例如：

```powershell
.venv\Scripts\python.exe -m scripts.atlas_backup --output F:\Backups\ResearchAtlas\atlas-2026-09-30.db
```

`--output` 必须显式指定，已存在的目标会被拒绝。默认源是 `ATLAS_DATABASE_URL` 指向的 SQLite 文件，或 `ATLAS_DATA\atlas.db`，未配置时为项目的 `data\atlas.db`。也可用 `--database` 显式指定源文件。该命令不导入 `backend.db`，不创建源数据库，不启动 worker，也不触发 schema 升级或业务初始化。

源库以只读方式打开；备份使用 SQLite backup API，因此正在使用 WAL 的数据库中已经提交的数据也会进入一致快照，无需直接复制 `.db` 或 WAL 文件。目标完成后重新只读打开，执行 `integrity_check` 和 `foreign_key_check`。默认备份超时 120 秒，大库可通过 `--timeout` 调整。

输出只有文件路径、字节数、schema 版本和检查状态，不输出设置内容或模型密钥。**数据库快照仍包含原数据库里的模型密钥和研究数据**，应保存在受控位置；此命令不会脱敏或清空设置。

这是 **database-only** 备份。PDF、原文缓存、附件、导入文件、`data/workspace` 镜像等文件应另行备份；仅恢复数据库不能恢复这些文件。升级前还应保留匹配的源代码版本。

## 离线恢复演练

先验证备份，不打开应用：

```powershell
.venv\Scripts\python.exe -m scripts.atlas_backup --verify F:\Backups\ResearchAtlas\atlas-2026-09-30.db
```

在新的空目录复制备份为 `atlas.db`，配合匹配代码与附件副本，在独立端口启动隔离实例；不要覆盖正在运行的生产库。检查论文、历史分析、笔记版本、附件打开和任务状态，再决定实际切换。恢复备份中的运行任务后，需检查现有进程与 ownership，不能直接重复执行分析。

实际生产切换应先停用所有数据库写入进程（包括独立分析脚本），保留当前库及其 WAL 文件，然后按明确的恢复方案切换。此工具只生成和验证快照，不执行覆盖、替换生产库或 worker 重启。
