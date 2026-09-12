import asyncio
from scratch.test_job_adapters import (
    RemoteOKAISource,
    ArbeitnowJobSource,
    JobicyAISource,
    HNWhoIsHiringJobSource,
    WeWorkRemotelyAISource,
    GitHubTechJobsSource
)

async def test():
    sources = [
        ("RemoteOKAI", RemoteOKAISource()),
        ("Arbeitnow", ArbeitnowJobSource()),
        ("Jobicy", JobicyAISource()),
        ("HNWhoIsHiring", HNWhoIsHiringJobSource()),
        ("WeWorkRemotely", WeWorkRemotelyAISource()),
        ("GitHubTechJobs", GitHubTechJobsSource()),
    ]
    total = 0
    for name, adapter in sources:
        urls = await adapter.discover_urls(1000)
        print(f"{name}: {len(urls)} discovered URLs")
        if urls:
            print(f"  Example: {urls[0]}")
        total += len(urls)
    print(f"\nTOTAL DISCOVERED JOB URLS: {total}")

if __name__ == "__main__":
    asyncio.run(test())
