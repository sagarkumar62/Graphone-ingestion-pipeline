import httpx
import json

def test_sources():
    # 1. Remotive API
    print("Testing Remotive API...")
    try:
        r = httpx.get("https://remotive.com/api/remote-jobs", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            print(f"Remotive API returned {len(jobs)} jobs")
            if jobs:
                print(f"  Example: {jobs[0].get('title')} at {jobs[0].get('company_name')} ({jobs[0].get('url')})")
    except Exception as e:
        print(f"Remotive error: {e}")

    # 2. HN Algolia API (Who is Hiring)
    print("\nTesting HN Algolia Who is Hiring API...")
    try:
        r = httpx.get("https://hn.algolia.com/api/v1/search?tags=author_whoishiring&hitsPerPage=5", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            hits = data.get("hits", [])
            print(f"HN WhoIsHiring stories found: {len(hits)}")
            if hits:
                story_id = hits[0].get("objectID")
                print(f"  Latest thread ID: {story_id} ({hits[0].get('title')})")
                r_comments = httpx.get(f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=500", timeout=10.0)
                if r_comments.status_code == 200:
                    comments = r_comments.json().get("hits", [])
                    print(f"  Comments in thread: {len(comments)}")
    except Exception as e:
        print(f"HN error: {e}")

if __name__ == "__main__":
    test_sources()
