import asyncio
import httpx
import re
from xml.etree import ElementTree as ET

async def audit_5_original_sources():
    sources = [
        ("AIJobsNet", "https://ai-jobs.net/"),
        ("YC Work at a Startup", "https://www.workatastartup.com/jobs"),
        ("RemoteOK AI", "https://remoteok.com/api"),
        ("We Work Remotely AI", "https://weworkremotely.com/categories/remote-programming-jobs.rss"),
        ("CryptoJobs AI", "https://cryptojobslist.com/ai"),
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for name, url in sources:
            print(f"\n==================== {name} ({url}) ====================")
            try:
                r = await client.get(url)
                print(f"HTTP Status: {r.status_code}")
                print(f"Content Length: {len(r.text)} bytes")

                if r.status_code == 200:
                    if "xml" in r.headers.get("content-type", "") or url.endswith(".rss"):
                        try:
                            root = ET.fromstring(r.text)
                            items = root.findall(".//item")
                            print(f"RSS items count: {len(items)}")
                            if items:
                                pub_date = items[0].find("pubDate")
                                print(f"Sample pubDate: {pub_date.text if pub_date is not None else 'None'}")
                        except Exception as ex:
                            print(f"RSS parse error: {ex}")
                    elif "json" in r.headers.get("content-type", "") or url.endswith("/api"):
                        try:
                            data = r.json()
                            if isinstance(data, list):
                                print(f"JSON list items count: {len(data)}")
                                if len(data) > 1 and isinstance(data[1], dict):
                                    print(f"Sample job date: {data[1].get('date')}")
                                    print(f"Sample job title: {data[1].get('position')}")
                        except Exception as ex:
                            print(f"JSON parse error: {ex}")
                    else:
                        # HTML
                        if "ai-jobs.net" in url:
                            matches = re.findall(r'href="(/job/[a-zA-Z0-9\-]+/?)"', r.text)
                            print(f"HTML job link matches: {len(set(matches))}")
                        elif "workatastartup" in url:
                            matches = re.findall(r'href="(/jobs/[0-9]+)"', r.text)
                            print(f"HTML job link matches: {len(set(matches))}")
                        elif "cryptojobslist" in url:
                            matches = re.findall(r'href="(/jobs/[a-zA-Z0-9\-]+/?)"', r.text)
                            print(f"HTML job link matches: {len(set(matches))}")
            except Exception as e:
                print(f"Error fetching {name}: {e}")

if __name__ == "__main__":
    asyncio.run(audit_5_original_sources())
