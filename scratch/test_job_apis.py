import httpx

def test_more_job_apis():
    apis = [
        "https://jobicy.com/api/v2/remote-jobs?count=100",
        "https://www.arbeitnow.com/api/job-board-api",
        "https://remoteok.com/api"
    ]
    for url in apis:
        try:
            r = httpx.get(url, timeout=10.0)
            print(f"{url}: Status {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    print("  dict keys:", list(data.keys()))
                    if "data" in data:
                        print("  items:", len(data["data"]))
                    elif "jobs" in data:
                        print("  items:", len(data["jobs"]))
                elif isinstance(data, list):
                    print("  list length:", len(data))
        except Exception as e:
            print(f"{url}: Error {e}")

if __name__ == "__main__":
    test_more_job_apis()
