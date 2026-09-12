import os
import json
import jsonschema
from src.core.config import settings
from src.core.models import RecordType
from src.core.exceptions import SchemaValidationException
from src.core.logging import logger

class JSONSchemaValidator:
    """
    Validates canonical JSON dictionaries against formal JSON Schemas stored in schemas/.
    """
    
    def __init__(self, schemas_dir: str | None = None):
        self.schemas_dir = schemas_dir or settings.SCHEMAS_DIR
        self._schemas: dict[str, dict] = {}
        self._load_schemas()

    def _load_schemas(self) -> None:
        """Loads all .schema.json files from the schemas directory into memory."""
        schema_mapping = {
            RecordType.STARTUP: "startup.schema.json",
            RecordType.PRODUCT: "product.schema.json",
            RecordType.RESEARCH_PAPER: "research-paper.schema.json",
            RecordType.JOB: "job.schema.json",
            RecordType.NEWS: "news.schema.json",
            RecordType.ENTITY_MAPPING: "entity-mapping.schema.json"
        }
        
        for record_type, filename in schema_mapping.items():
            path = os.path.join(self.schemas_dir, filename)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._schemas[record_type.value] = json.load(f)
            else:
                logger.warning(f"Schema file not found at {path}")

    def validate(self, instance: dict, record_type: RecordType | str) -> tuple[bool, list[str]]:
        """
        Validates a payload dictionary against its corresponding RecordType schema.
        Returns (is_valid, error_messages).
        Raises SchemaValidationException if validation fails when strict=True.
        """
        type_str = record_type.value if isinstance(record_type, RecordType) else str(record_type)
        schema = self._schemas.get(type_str)
        
        if not schema:
            err = f"No schema registered for record type '{type_str}'"
            return False, [err]

        validator = jsonschema.Draft7Validator(schema)
        errors = [err.message for err in validator.iter_errors(instance)]
        
        if errors:
            logger.error("Schema validation failed", extra={"record_type": type_str, "errors": errors[:3]})
            return False, errors
            
        return True, []

    def validate_or_raise(self, instance: dict, record_type: RecordType | str) -> None:
        is_valid, errors = self.validate(instance, record_type)
        if not is_valid:
            raise SchemaValidationException(
                message=f"Payload failed {record_type} schema validation",
                errors=errors
            )

validator = JSONSchemaValidator()
