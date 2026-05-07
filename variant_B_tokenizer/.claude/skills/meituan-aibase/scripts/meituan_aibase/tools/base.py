"""
Tools 基类
version: 0.2.0
"""
import json
import logging
from typing import Optional, Any
from ..config import AIBASE_BRANCH_URL, AIBASE_BRANCH_KEY, READ_ONLY
from ..platform.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


def read_only_check(fn):
    """装饰器：READ_ONLY=true 时拒绝写操作"""
    import functools
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        if READ_ONLY:
            return json.dumps(
                {"success": False, "error": "当前处于只读模式（READ_ONLY=true），写操作已被拒绝"},
                ensure_ascii=False,
            )
        return await fn(*args, **kwargs)
    return wrapper


def handle_errors(fn):
    """装饰器：统一捕获异常并返回 JSON 错误"""
    import functools
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            result = await fn(*args, **kwargs)
            if isinstance(result, str):
                return result
            return json.dumps({"success": True, "data": result}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[{fn.__name__}] 执行失败: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    return wrapper


def to_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


class BaseTools:
    """所有 Tools 的基类，提供 Supabase 客户端获取逻辑"""

    def __init__(self, aibase_client, branch_url: Optional[str] = None, branch_key: Optional[str] = None):
        self.aibase_client = aibase_client
        # 优先使用传入值，其次环境变量
        self._branch_url = branch_url or AIBASE_BRANCH_URL
        self._branch_key = branch_key or AIBASE_BRANCH_KEY
        self._supabase_client: Optional[SupabaseClient] = None

    async def _get_client(self) -> SupabaseClient:
        """
        获取 Supabase 客户端（懒加载）。

        URL 和 Key 的获取优先级：
          1. 实例化时传入的 branch_url / branch_key（或对应环境变量 AIBASE_BRANCH_URL / AIBASE_BRANCH_KEY）
          2. 从管控面 branch 详情自动获取（调 _get_default_branch → 取 domain / serviceRoleKey）

        URL 和 Key 均来自 branch 详情，不依赖手动拼接域名。
        """
        if self._supabase_client is None:
            url = self._branch_url
            key = self._branch_key

            # fallback：从管控面默认 branch 获取 domain 和 serviceRoleKey
            if not url or not key:
                branch = self.aibase_client._get_default_branch()
                if branch:
                    if not url:
                        url = branch.get("domain")
                    if not key:
                        key = branch.get("serviceRoleKey")

            if not url or not key:
                raise ValueError(
                    "无法获取数据库连接信息。\n"
                    "请先运行 list-branches 确认目标 branch 状态为 RUNNING，\n"
                    "然后设置环境变量：\n"
                    "  AIBASE_BRANCH_URL=<branch.domain>\n"
                    "  AIBASE_BRANCH_KEY=<branch.serviceRoleKey>"
                )

            self._supabase_client = SupabaseClient(url=url, key=key)
        return self._supabase_client

    async def close(self) -> None:
        if self._supabase_client:
            await self._supabase_client.close()
