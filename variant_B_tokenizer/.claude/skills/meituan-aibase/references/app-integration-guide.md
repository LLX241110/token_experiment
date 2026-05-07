# AI Base 应用接入指南

AI Base **100% 兼容 Supabase 客户端 SDK**，将 Supabase endpoint/key 替换为 AI Base 的即可接入。

## 获取连接信息

从 AI Base 控制台申请 workspace 后，可获得：
- `AIBASE_WORKSPACE_URL` — Supabase 兼容的 API endpoint
- `AIBASE_WORKSPACE_KEY` — service_role 或 anon key

## TypeScript / JavaScript 接入

```typescript
import { createClient } from '@supabase/supabase-js'
import type { Database } from './database.types'  // 通过 generate-typescript-types 生成

const supabase = createClient<Database>(
  process.env.AIBASE_WORKSPACE_URL!,
  process.env.AIBASE_WORKSPACE_KEY!
)

// 查询
const { data, error } = await supabase
  .from('users')
  .select('*')
  .limit(10)

// 插入
const { data, error } = await supabase
  .from('todos')
  .insert({ title: '新任务', done: false })
  .select()

// 更新
const { data, error } = await supabase
  .from('todos')
  .update({ done: true })
  .eq('id', 1)

// 删除
const { error } = await supabase
  .from('todos')
  .delete()
  .eq('id', 1)
```

## Python 接入

```python
# TODO: 将 supabase 包替换为美团内部 pip 源
from supabase import create_client, Client
import os

url = os.environ["AIBASE_WORKSPACE_URL"]
key = os.environ["AIBASE_WORKSPACE_KEY"]
client: Client = create_client(url, key)

# 查询
response = client.table("users").select("*").limit(10).execute()
print(response.data)

# 插入
response = client.table("todos").insert({"title": "新任务", "done": False}).execute()
```

## 直接调用 PostgREST API

AI Base 暴露标准 PostgREST REST API：

```bash
# 查询
curl "${AIBASE_WORKSPACE_URL}/rest/v1/users?select=*&limit=5" \
  -H "apikey: ${AIBASE_WORKSPACE_KEY}" \
  -H "Authorization: Bearer ${AIBASE_WORKSPACE_KEY}"

# 插入
curl -X POST "${AIBASE_WORKSPACE_URL}/rest/v1/todos" \
  -H "apikey: ${AIBASE_WORKSPACE_KEY}" \
  -H "Authorization: Bearer ${AIBASE_WORKSPACE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"title": "新任务", "done": false}'
```

> 端点差异说明见 `tool-reference.md`。通过 Skill CLI（`execute-sql` / `apply-migration`）会自动选择正确端点，无需手动区分。

## 执行原生 SQL

```bash
uv run ./scripts/call_meituan_aibase.py execute-sql \
  --query "SELECT count(*) FROM users WHERE created_at > now() - interval '7 days'"
```

## RLS（行级安全策略）

参考：[rls-guide.md](rls-guide.md)

## 注意事项

- AI Base 初版不支持 Storage 和 Edge Function，相关 SDK 方法调用会报错
- service_role key 拥有绕过 RLS 的权限，生产环境客户端请使用 anon key + RLS
- AI Base 100% 兼容 Supabase，官方文档 https://supabase.com/docs 同样适用
