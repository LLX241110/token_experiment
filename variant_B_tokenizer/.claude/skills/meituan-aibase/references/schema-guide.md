# AI Base Schema 设计规范

AI Base 基于 PostgreSQL，以下规范均与标准 Supabase 兼容。

## 建表规范

```sql
-- 推荐：使用 UUID 主键 + 时间戳
CREATE TABLE todos (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    title       text        NOT NULL,
    done        boolean     NOT NULL DEFAULT false,
    user_id     uuid        REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER todos_updated_at
    BEFORE UPDATE ON todos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

## 迁移管理

AI Base 使用 `supabase_migrations.schema_migrations` 表追踪迁移版本：

```bash
# 执行迁移（自动添加版本记录）
uv run ./scripts/call_meituan_aibase.py apply-migration \
  --name "create_todos_table" \
  --query-file ./migrations/001_create_todos.sql

# 查看迁移记录
uv run ./scripts/call_meituan_aibase.py list-migrations
```

## 常用类型对应

| 场景 | PostgreSQL 类型 | TypeScript 类型 |
|------|----------------|----------------|
| 主键 | `uuid` | `string` |
| 短文本 | `text` / `varchar(n)` | `string` |
| 整数 | `integer` / `bigint` | `number` |
| 小数 | `numeric` / `decimal` | `number` |
| 布尔 | `boolean` | `boolean` |
| JSON | `jsonb` | `Json` |
| 时间戳 | `timestamptz` | `string` |
| 数组 | `text[]` / `integer[]` | `string[]` / `number[]` |

## 生成 TypeScript 类型

```bash
uv run ./scripts/call_meituan_aibase.py generate-typescript-types \
  --schemas "public,auth" > database.types.ts
```

## 索引建议

```sql
-- 外键索引（PostgreSQL 不自动创建）
CREATE INDEX idx_todos_user_id ON todos(user_id);

-- 全文检索索引
CREATE INDEX idx_todos_title_fts ON todos USING gin(to_tsvector('chinese', title));

-- 时间范围查询
CREATE INDEX idx_todos_created_at ON todos(created_at DESC);
```
