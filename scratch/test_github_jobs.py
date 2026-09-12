import httpx
import json

def test_github_job_repos():
    # SimplifyJobs / New-Grad-Positions or Summer2025-Internships
    urls = [
        "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/main/README.md",
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/main/README.md",
        "https://raw.githubusercontent.com/pittcsc/Summer2025-Internships/master/README.md"
    ]
    for url in urls:
        try:
            r = httpx.get(url, timeout=10.0)
            print(f"{url}: Status {r.status_code}, Length {len(r.text)}")
        except Exception as e:
            print(f"{url}: Error {e}")

if __name__ == "__main__":
    test_github_job_repos()
