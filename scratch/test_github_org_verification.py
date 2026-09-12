import asyncio
import httpx
import json

async def test_github_org_details():
    # Test fetching org details for known AI startups / companies on GitHub
    sample_orgs = ["openai", "anthropic", "cohere-ai", "mistralai", "stability-ai", "huggingface", "xai-org", "deepseek-ai", "qwen-ai", "replicate"]

    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        for org in sample_orgs:
            try:
                res = await client.get(f"https://api.github.com/orgs/{org}")
                if res.status_code == 200:
                    data = res.json()
                    print(f"Org: {data.get('login')} | Name: {data.get('name')} | Blog: {data.get('blog')} | Location: {data.get('location')} | Verified: {data.get('is_verified')}")
                    print(f"  Description: {data.get('description')}")
            except Exception as e:
                print(f"Error fetching {org}: {e}")

if __name__ == "__main__":
    asyncio.run(test_github_org_details())
