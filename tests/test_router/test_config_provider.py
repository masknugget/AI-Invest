# main.py 或 app.py
import asyncio
from app.services.config.config_provider import provider as config_provider

async def main():
    """异步调用配置服务"""
    # ✅ 正确的异步调用方式
    settings = await config_provider.get_effective_system_settings()
    print(f"系统配置: {settings}")
    return settings

# 运行异步主函数
if __name__ == "__main__":
    asyncio.run(main())