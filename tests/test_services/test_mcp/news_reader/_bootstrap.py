"""
News Reader MCP 工具示例公共引导（非 mock）。

只做三件事，保证示例脚本能离线导入、并真实调用后端：
1. 项目根加入 sys.path + 加载根目录 .env + Windows 控制台 UTF-8
2. 以命名空间包形式预注册 recommender 相关目录，跳过 recommender/__init__.py
   （它会拉起 batch_generator 的 MongoDB + LLM 批处理），但 **不打桩** consumer.news，
   因此流水线 / 分析师工具走的是真实的 recommender.news_reader 实现
3. 提供 MongoDB 连接初始化 / 关闭的小工具，供需要落库 / 检索的示例使用

用法：在示例脚本顶部 `import _bootstrap`（或 from _bootstrap import ...），
      之后再 import 被测工具模块。
"""
import asyncio
import io
import json
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows 控制台 UTF-8，避免中文输出乱码
if sys.platform == "win32":
    import ctypes

    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 可选加载项目根 .env（不存在则忽略）—— 真实调用需要有效 LLM key
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except Exception:
    pass


def _register_pkg(name: str, dir_path: Path) -> types.ModuleType:
    """以空命名空间包形式注册真实目录，跳过重量级 __init__ 副作用。"""
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(dir_path)]
    sys.modules[name] = pkg
    return pkg


def _skip_heavy_recommender_init() -> None:
    """注册 recommender 相关命名空间包，避免拉起 batch_generator。

    仅父包用命名空间形式绕开 __init__.py；真正的实现模块
    （recommender.news_reader.consumer.news / agents.analyst.factory 等）
    仍从真实目录正常导入并执行 —— 即真实调用。
    """
    if "recommender" in sys.modules:
        return
    nr_root = PROJECT_ROOT / "recommender" / "news_reader"
    recommender = _register_pkg("recommender", PROJECT_ROOT / "recommender")
    news_reader_pkg = _register_pkg("recommender.news_reader", nr_root)
    _register_pkg("recommender.news_reader.agents", nr_root / "agents")
    _register_pkg(
        "recommender.news_reader.agents.analyst", nr_root / "agents" / "analyst"
    )
    recommender.news_reader = news_reader_pkg
    news_reader_pkg.news_reader = news_reader_pkg


_skip_heavy_recommender_init()

# 被测工具包（真实实现，未打桩）
from app.services.mcp.tools import news_reader  # noqa: E402
from app.services.mcp.tools.news_reader import (  # noqa: E402
    analysts,
    contract,
    insights,
    pipeline,
)


def run(coro_or_value):
    """同步执行协程或直接返回普通值（不引入 pytest）。"""
    if asyncio.iscoroutine(coro_or_value):
        return asyncio.run(coro_or_value)
    return coro_or_value


def parse(resp: str) -> dict:
    """解析工具返回的 JSON 字符串响应并美化打印用。"""
    return json.loads(resp)


async def init_db() -> None:
    """初始化 MongoDB / Redis 连接（落库、检索类示例需要）。"""
    from app.core.database import init_database

    await init_database()


async def close_db() -> None:
    from app.core.database import close_database

    await close_database()


def banner(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


__all__ = [
    "PROJECT_ROOT",
    "news_reader",
    "contract",
    "pipeline",
    "analysts",
    "insights",
    "run",
    "parse",
    "init_db",
    "close_db",
    "banner",
]
