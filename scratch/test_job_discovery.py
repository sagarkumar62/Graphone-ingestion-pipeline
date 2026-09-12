import asyncio
from src.sources.job_sources import (
    AIJobsNetSource,
    YCWorkAtAStartupSource,
    RemoteOKAISource,
    WeWorkRemotelyAISource,
    CryptoJobsAISource
)

async def test():
    sources = [
        ("AIJobsNet", AIJobsNetSource()),
        ("YCWorkAtAStartup", YCWorkAtAStartupSource()),
        ("RemoteOKAI", RemoteOKAISource()),
        ("WeWorkRemotelyAI", WeWorkRemotelyAISource()),
        ("CryptoJobsAI", CryptoJobsAISource()),
    ]
    for name, adapter in sources:
        urls = await adapter.discover_urls(2000)
        print(f"{name}: {len(urls)} URLs discovered")
        if urls:
            print(f"  Example: {urls[0]}")

if __name__ == "__main__":
    asyncio.run(test())
