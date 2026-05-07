# Workflows

## 1. 初次接入

1. 运行 `list-workspaces` 获取 `domain`、`serviceRoleKey`、`uuid`
2. 设置环境变量：
   ```bash
   export AIBASE_WORKSPACE_URL="<domain>"
   export AIBASE_WORKSPACE_KEY="<serviceRoleKey>"
   ```
3. 运行 `list-tables` 确认连通性
4. 运行 `describe-workspace` 查看 workspace 状态

## 2. 建表（标准迁移流程）

1. 参考 `schema-guide.md` 设计表结构（UUID 主键、timestamptz、外键索引等）
2. 用 `apply-migration` 执行 DDL：
   ```bash
   uv run ./scripts/call_meituan_aibase.py apply-migration \
     --name "create_<table>_table" \
     --query "<DDL SQL>"
   ```
3. 运行 `list-tables` 确认表已创建
4. 运行 `list-migrations` 确认迁移记录

## 3. 数据库排障

1. `list-tables` 确认 schema / table 存在
2. `list-extensions` 确认依赖扩展是否启用
3. `execute-sql` 做临时诊断查询
4. 如需变更 schema，用 `apply-migration`（不要用 `execute-sql` 做 DDL，避免丢失迁移记录）

## 4. 应用接入

1. 从 `list-workspaces` 或 `get-keys --reveal` 获取 `anonKey`（前端）或 `serviceRoleKey`（后端）
2. 参考 `app-integration-guide.md` 初始化 Supabase SDK
3. 生产环境前端使用 `anonKey` + RLS，不要暴露 `serviceRoleKey`
4. 参考 `rls-guide.md` 配置行级安全策略

## 5. 成员管理

1. 运行 `list-workspaces` 确认目标 workspace uuid
2. `list-members --workspace-uuid <uuid>` 查看当前成员
3. 用 `add-members` / `remove-members` 增删，或 `replace-members` 全量覆盖
4. 再次 `list-members` 确认结果
