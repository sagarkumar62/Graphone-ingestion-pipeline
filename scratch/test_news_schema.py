from src.validators.schema_validator import validator
from src.core.models import RecordType, RawPayload
from src.sources.news_sources import HuggingFaceDailyPapersSource

adapter = HuggingFaceDailyPapersSource()
payload = adapter.parse_raw_payload(RawPayload(
    source_name='HuggingFaceDailyPapers',
    url='https://huggingface.co/papers/2609.10745',
    raw_content='<html><body><article><p>Test article content here...</p></article></body></html>',
    content_type='text/html'
))
print('Payload content:', payload['content'])
is_valid, errors = validator.validate(payload, RecordType.NEWS)
print('Is Valid:', is_valid)
print('Errors:', errors)
