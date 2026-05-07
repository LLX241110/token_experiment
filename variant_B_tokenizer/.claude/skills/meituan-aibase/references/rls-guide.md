# AI Base RLS（行级安全策略）配置指南

AI Base 支持 PostgreSQL 标准 RLS，与 Supabase 完全兼容。

## 启用 RLS

```sql
-- 启用表的行级安全
ALTER TABLE todos ENABLE ROW LEVEL SECURITY;

-- 强制对所有角色生效（包括 service_role）
ALTER TABLE todos FORCE ROW LEVEL SECURITY;
```

## 常用策略模板

### 用户只能访问自己的数据

```sql
-- 查询：只能看到自己的记录
CREATE POLICY "users_select_own" ON todos
    FOR SELECT
    USING (user_id = auth.uid());

-- 插入：只能插入自己的记录
CREATE POLICY "users_insert_own" ON todos
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- 更新：只能修改自己的记录
CREATE POLICY "users_update_own" ON todos
    FOR UPDATE
    USING (user_id = auth.uid());

-- 删除：只能删除自己的记录
CREATE POLICY "users_delete_own" ON todos
    FOR DELETE
    USING (user_id = auth.uid());
```

### 公开读，登录可写

```sql
CREATE POLICY "public_read" ON posts
    FOR SELECT USING (true);

CREATE POLICY "auth_insert" ON posts
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');
```

### 管理员全权限

```sql
CREATE POLICY "admin_all" ON todos
    FOR ALL
    USING (auth.jwt() ->> 'role' = 'admin');
```

## 注意事项

- `service_role` key 默认绕过 RLS，生产环境前端请使用 `anon` key
- RLS 策略可叠加，满足任意一条即可访问
- 通过 `apply-migration` 执行 DDL 时，`service_role` 不受 RLS 限制

## 验证 RLS

```bash
# 以 anon 角色验证
uv run ./scripts/call_meituan_aibase.py execute-sql \
  --query "SET LOCAL ROLE anon; SELECT * FROM todos LIMIT 5;"
```
