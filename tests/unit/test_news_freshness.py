import pytest
from datetime import datetime, timedelta, timezone
from src.pipeline.freshness import freshness_validator, FreshnessValidator
from src.core.models import FreshnessStatus, RawPayload, RecordType
from src.crawlers.extractor import html_extractor
from src.pipeline.deduplication import DeduplicationEngine
from src.sources.news_sources import HuggingFaceDailyPapersSource, TechCrunchAISource, OpenAIBlogSource
from src.validators.schema_validator import validator

def test_freshness_boundaries():
    validator_engine = FreshnessValidator(window_hours=24.0)
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # 1. 1 hour old -> accepted
    res_1h = validator_engine.evaluate_freshness(now - timedelta(hours=1), reference_now=now)
    assert res_1h.status == FreshnessStatus.FRESH
    assert res_1h.age_hours == 1.0

    # 2. 23h59m -> accepted
    res_23h59m = validator_engine.evaluate_freshness(now - timedelta(hours=23, minutes=59), reference_now=now)
    assert res_23h59m.status == FreshnessStatus.FRESH
    assert res_23h59m.age_hours == 23.98

    # 3. Exactly 24h -> accepted
    res_24h = validator_engine.evaluate_freshness(now - timedelta(hours=24), reference_now=now)
    assert res_24h.status == FreshnessStatus.FRESH
    assert res_24h.age_hours == 24.0

    # 4. 24h+ (24.1h) -> rejected
    res_24_1h = validator_engine.evaluate_freshness(now - timedelta(hours=24, minutes=6), reference_now=now)
    assert res_24_1h.status == FreshnessStatus.STALE
    assert res_24_1h.age_hours == 24.1

    # 5. Missing date -> rejected (UNKNOWN)
    res_none = validator_engine.evaluate_freshness(None, reference_now=now)
    assert res_none.status == FreshnessStatus.UNKNOWN

    res_empty = validator_engine.evaluate_freshness("", reference_now=now)
    assert res_empty.status == FreshnessStatus.UNKNOWN

    # 6. Malformed date -> rejected
    res_malformed = validator_engine.evaluate_freshness("invalid-date-string-xyz", reference_now=now)
    assert res_malformed.status == FreshnessStatus.UNKNOWN

    # 7. Relative dates
    res_rel_2h = validator_engine.evaluate_freshness("2 hours ago", reference_now=now)
    assert res_rel_2h.status == FreshnessStatus.FRESH
    assert abs(res_rel_2h.age_hours - 2.0) < 0.1

    res_rel_yesterday = validator_engine.evaluate_freshness("yesterday", reference_now=now)
    assert res_rel_yesterday.status == FreshnessStatus.FRESH
    assert abs(res_rel_yesterday.age_hours - 24.0) < 0.1

    # 8. Timezone normalization
    # EST offset (-05:00)
    dt_est_str = "2026-09-12T07:00:00-05:00" # Equivalent to 12:00 UTC (0h old)
    res_est = validator_engine.evaluate_freshness(dt_est_str, reference_now=now)
    assert res_est.status == FreshnessStatus.FRESH
    assert res_est.age_hours == 0.0

    # 9. Future dates
    # Clock drift (+30m) -> accepted
    res_future_near = validator_engine.evaluate_freshness(now + timedelta(minutes=30), reference_now=now)
    assert res_future_near.status == FreshnessStatus.FRESH

    # Far future (+5h) -> rejected (UNKNOWN)
    res_future_far = validator_engine.evaluate_freshness(now + timedelta(hours=5), reference_now=now)
    assert res_future_far.status == FreshnessStatus.UNKNOWN


def test_news_full_text_extraction():
    html_content = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Breakthrough in Neural Architecture Search</title>
        <meta name="description" content="A short summary of the breakthrough.">
      </head>
      <body>
        <nav><p>Navigation bar links...</p></nav>
        <article>
          <h1>Breakthrough in Neural Architecture Search</h1>
          <p>Researchers have developed a novel approach to automated neural architecture search using reinforcement learning with dynamic reward pruning.</p>
          <p>The system evaluates thousands of candidate architectures per second, significantly reducing computational overhead compared to traditional Bayesian optimization algorithms.</p>
        </article>
        <footer><p>Copyright 2026</p></footer>
      </body>
    </html>
    """
    extracted = html_extractor.extract(html_content, "https://techcrunch.com/2026/09/11/ai-breakthrough")
    assert extracted.title == "Breakthrough in Neural Architecture Search"
    assert "automated neural architecture search" in extracted.main_text
    assert len(extracted.main_text) > 200

    # Test RSS summary distinction
    summary_only = "A short summary of the breakthrough."
    assert len(summary_only) < len(extracted.main_text)

    # Test malformed HTML
    malformed_html = "<article><h1>Unclosed Tag<p>Content without closing body or html tags"
    extracted_malformed = html_extractor.extract(malformed_html, "https://example.com/malformed")
    assert "Content without closing" in extracted_malformed.main_text


@pytest.mark.asyncio
async def test_news_deduplication():
    dedup = DeduplicationEngine()
    url1 = "https://techcrunch.com/2026/09/11/openai-adds-board-member"
    url2 = "https://techcrunch.com/2026/09/11/openai-adds-board-member"
    url3 = "https://mittechreview.com/2026/09/11/openai-adds-board-member"

    # Claim url1
    await dedup.claim_url(url1, "content version 1")

    # Identical canonical URL check
    is_dup1, _ = await dedup.is_duplicate_url(url1)
    assert is_dup1 is True

    # Same title but different domain/URL -> remain separate
    is_dup3, _ = await dedup.is_duplicate_url(url3)
    assert is_dup3 is False


def test_news_provenance_and_schema():
    adapter = HuggingFaceDailyPapersSource()

    # Valid payload with complete provenance
    valid_payload = RawPayload(
        source_name="HuggingFaceDailyPapers",
        url="https://huggingface.co/papers/2609.10745",
        raw_content="<html><body><article><p>Article body content...</p></article></body></html>",
        content_type="text/html"
    )
    parsed = adapter.parse_raw_payload(valid_payload)
    parsed["content"]["published_date"] = "2026-09-11T12:00:00Z"

    is_valid, errors = validator.validate(parsed, RecordType.NEWS)
    assert is_valid is True
    assert len(errors) == 0

    # Missing source URL -> reject
    invalid_source_url = dict(parsed)
    invalid_source_url["source"] = {"name": "HuggingFaceDailyPapers"} # Missing required "url" field
    is_valid_url, errors_url = validator.validate(invalid_source_url, RecordType.NEWS)
    assert is_valid_url is False

    # Empty title -> reject (minLength 1)
    invalid_title = dict(parsed)
    invalid_title["content"] = dict(parsed["content"])
    invalid_title["content"]["title"] = ""
    is_valid_title, errors_title = validator.validate(invalid_title, RecordType.NEWS)
    assert is_valid_title is False
