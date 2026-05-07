"""
AI Base Supabase 客户端封装
version: 0.3.7

使用官方 supabase-py 客户端，endpoint 指向美团 AI Base 服务。
TODO: pip 源替换为美团内部源后更新 requirements.txt。
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AiBaseApiError(Exception):
    def __init__(self, status_code: int, path: str, endpoint: str, payload: Any):
        self.status_code = status_code
        self.path = path
        self.endpoint = endpoint
        self.payload = payload
        import json
        super().__init__(
            json.dumps(
                {
                    "status_code": status_code,
                    "path": path,
                    "endpoint": endpoint,
                    "error": payload,
                },
                ensure_ascii=False,
            )
        )


class SupabaseClient:
    """
    AI Base REST 客户端，通过 PostgREST 执行 SQL 和数据库操作。
    AI Base 100% 兼容 Supabase API 协议。

    TODO: 当美团内部 supabase-py 镜像地址确认后，
          将 requirements.txt 中的 supabase 包替换为内部源地址。
    """

    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self._http_client = None

    async def _get_http_client(self):
        """懒加载 httpx 异步客户端"""
        if self._http_client is None or self._http_client.is_closed:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(
                    timeout=30.0,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                    verify=False,
                )
            except ImportError:
                raise ImportError(
                    "httpx 未安装。请运行：uv pip install -r requirements.txt"
                )
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    def _default_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    async def call_api(
        self,
        path: str,
        method: str = "GET",
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: float = 30.0,
    ) -> Any:
        """
        底层 HTTP 请求方法，兼容 PostgREST API 协议。
        """
        import httpx

        url = f"{self.url}{path}"
        merged_headers = self._default_headers()
        if headers:
            merged_headers.update(headers)

        client = await self._get_http_client()

        for attempt in range(3):
            try:
                response = await client.request(
                    method,
                    url,
                    json=json_data,
                    headers=merged_headers,
                    params=params,
                    timeout=timeout,
                )
                response.raise_for_status()

                if response.status_code == 204 or not response.content:
                    return {"success": True}

                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip()
                if "application/json" in content_type or mime.endswith("+json"):
                    return response.json()
                return {"raw": response.text}

            except httpx.HTTPStatusError as e:
                resp = e.response
                if resp.status_code in {502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                try:
                    payload = resp.json()
                except Exception:
                    payload = resp.text

                # 404：workspace 实例未就绪
                if resp.status_code == 404:
                    raise AiBaseApiError(
                        status_code=404,
                        path=path,
                        endpoint=self.url,
                        payload=(
                            "Workspace 连接失败（404）：服务路径不存在。\n"
                            "可能原因：workspace 实例尚未就绪（新建 workspace 需要几分钟初始化），"
                            "请稍后重试或联系 AI Base 平台确认实例状态。\n"
                            f"请求地址：{self.url}{path}"
                        ),
                    ) from e

                # 401/403：鉴权失败
                if resp.status_code in {401, 403}:
                    raise AiBaseApiError(
                        status_code=resp.status_code,
                        path=path,
                        endpoint=self.url,
                        payload=(
                            f"Workspace 鉴权失败（{resp.status_code}）：\n"
                            "请检查 AIBASE_BRANCH_KEY 是否为 service_role key（非 anon key），"
                            "以及 MOA 登录态是否已过期。\n"
                            f"原始响应：{payload}"
                        ),
                    ) from e

                raise AiBaseApiError(
                    status_code=resp.status_code,
                    path=path,
                    endpoint=self.url,
                    payload=payload,
                ) from e

            except httpx.TransportError as e:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise Exception(
                    f"Workspace 连接超时或网络不通：{type(e).__name__}: {e}\n"
                    f"请确认在美团内网环境中，且 AIBASE_BRANCH_URL={self.url} 与 branch.domain 一致。"
                ) from e
