from typing import Any
from src.resolver.normalizer import normalizer
from src.resolver.seed import CANONICAL_SEED_RECORDS, generate_seed_entity_id
from src.core.models import ResolutionDecision, CanonicalEntityRecord
from src.core.logging import logger

class ResolutionResult:
    def __init__(
        self,
        raw_value: str,
        normalized_value: str,
        canonical_value: str,
        canonical_entity_id: str | None,
        decision: ResolutionDecision | str,
        match_method: str,
        confidence: float,
        evidence: dict[str, Any] | None = None
    ):
        self.raw_value = raw_value
        self.normalized_value = normalized_value
        self.canonical_value = canonical_value
        self.canonical_entity_id = canonical_entity_id
        self.decision = decision.value if isinstance(decision, ResolutionDecision) else decision
        self.match_method = match_method
        self.confidence = confidence
        self.evidence = evidence or {}

class DeterministicEntityResolver:
    """
    Deterministic Entity Resolution Engine matching raw incoming entity representations
    to canonical master records without using LLMs for primary matching decisions.
    
    5-Tier Priority Hierarchy (O(1) / O(log N) indexed lookups):
    Level 1 — Exact Stable External Identifier (Crunchbase ID, Wikidata ID, GitHub Org ID)
    Level 2 — Exact Canonical Domain Ownership (e.g., 'openai.com')
    Level 3 — Exact Normalized Name Match
    Level 4 — Exact Known Alias Match
    Level 5 — Deterministic Composite Evidence Match
    Fallback — NO_MATCH / AMBIGUOUS / REVIEW_REQUIRED (False-merge prevention)
    """

    def __init__(self, seed_records: list[CanonicalEntityRecord] | None = None):
        self.normalizer = normalizer
        self.records: list[CanonicalEntityRecord] = seed_records or CANONICAL_SEED_RECORDS

        # Indexed O(1) Lookup Hash Maps
        self._external_id_index: dict[tuple[str, str], CanonicalEntityRecord] = {}
        self._domain_index: dict[str, CanonicalEntityRecord] = {}
        self._name_index: dict[tuple[str, str], CanonicalEntityRecord] = {}
        self._alias_index: dict[tuple[str, str], CanonicalEntityRecord] = {}

        self._build_indexes()

    def _build_indexes(self):
        self._external_id_index.clear()
        self._domain_index.clear()
        self._name_index.clear()
        self._alias_index.clear()

        for record in self.records:
            # 1. External IDs
            for ext_key, ext_val in record.external_ids.items():
                if ext_val:
                    idx_key = (ext_key.lower().strip(), ext_val.lower().strip())
                    self._external_id_index[idx_key] = record

            # 2. Canonical Domains
            for domain in record.domains:
                norm_dom = self.normalizer.normalize_domain(domain)
                if norm_dom:
                    self._domain_index[norm_dom] = record

            # 3. Exact Normalized Name
            norm_name = self.normalizer.normalize(record.canonical_name)
            self._name_index[(record.entity_type.upper(), norm_name)] = record
            self._name_index[("ANY", norm_name)] = record

            # 4. Exact Aliases
            for alias in record.aliases:
                norm_alias = self.normalizer.normalize(alias)
                if norm_alias:
                    self._alias_index[(record.entity_type.upper(), norm_alias)] = record
                    self._alias_index[("ANY", norm_alias)] = record

    def register_canonical_entity(self, record: CanonicalEntityRecord):
        """Idempotently adds/updates a canonical entity in the active index."""
        existing_idx = None
        for idx, rec in enumerate(self.records):
            if rec.canonical_entity_id == record.canonical_entity_id:
                existing_idx = idx
                break
        if existing_idx is not None:
            self.records[existing_idx] = record
        else:
            self.records.append(record)
        self._build_indexes()

    def resolve(
        self,
        raw_name: str,
        entity_type: str = "STARTUP",
        domain: str | None = None,
        external_ids: dict[str, str] | None = None,
        source_url: str | None = None
    ) -> ResolutionResult:
        if not raw_name or not raw_name.strip():
            return ResolutionResult(
                raw_value="",
                normalized_value="",
                canonical_value="Unknown Entity",
                canonical_entity_id=None,
                decision=ResolutionDecision.NO_MATCH,
                match_method="EMPTY_INPUT",
                confidence=0.0,
                evidence={"empty_input": True}
            )

        raw_clean = raw_name.strip()
        normalized = self.normalizer.normalize(raw_clean)
        norm_type = entity_type.upper().strip()
        norm_domain = self.normalizer.normalize_domain(domain or source_url or "")

        # ---------------------------------------------------------------------
        # Level 1: Exact Stable External Identifier Match
        # ---------------------------------------------------------------------
        if external_ids:
            for ext_key, ext_val in external_ids.items():
                if ext_val:
                    idx_key = (ext_key.lower().strip(), ext_val.lower().strip())
                    if idx_key in self._external_id_index:
                        matched = self._external_id_index[idx_key]
                        return ResolutionResult(
                            raw_value=raw_clean,
                            normalized_value=normalized,
                            canonical_value=matched.canonical_name,
                            canonical_entity_id=matched.canonical_entity_id,
                            decision=ResolutionDecision.EXACT_EXTERNAL_ID_MATCH,
                            match_method=f"EXTERNAL_ID_{ext_key.upper()}",
                            confidence=1.0,
                            evidence={
                                "external_id_type": ext_key,
                                "external_id_value": ext_val,
                                "matched_canonical_id": matched.canonical_entity_id
                            }
                        )

        # ---------------------------------------------------------------------
        # Level 2: Exact Canonical Domain Match
        # ---------------------------------------------------------------------
        if norm_domain and norm_domain in self._domain_index:
            matched = self._domain_index[norm_domain]
            return ResolutionResult(
                raw_value=raw_clean,
                normalized_value=normalized,
                canonical_value=matched.canonical_name,
                canonical_entity_id=matched.canonical_entity_id,
                decision=ResolutionDecision.DOMAIN_MATCH,
                match_method="EXACT_DOMAIN_MATCH",
                confidence=1.0,
                evidence={
                    "domain": norm_domain,
                    "matched_canonical_id": matched.canonical_entity_id
                }
            )

        # ---------------------------------------------------------------------
        # Level 3: Exact Normalized Name Match
        # ---------------------------------------------------------------------
        for type_key in (norm_type, "ANY"):
            name_key = (type_key, normalized)
            if name_key in self._name_index:
                matched = self._name_index[name_key]
                return ResolutionResult(
                    raw_value=raw_clean,
                    normalized_value=normalized,
                    canonical_value=matched.canonical_name,
                    canonical_entity_id=matched.canonical_entity_id,
                    decision=ResolutionDecision.EXACT_NAME_MATCH,
                    match_method="EXACT_NAME_MATCH",
                    confidence=1.0,
                    evidence={
                        "normalized_name": normalized,
                        "matched_canonical_id": matched.canonical_entity_id
                    }
                )

        # ---------------------------------------------------------------------
        # Level 4: Exact Known Alias Match
        # ---------------------------------------------------------------------
        for type_key in (norm_type, "ANY"):
            alias_key = (type_key, normalized)
            if alias_key in self._alias_index:
                matched = self._alias_index[alias_key]
                return ResolutionResult(
                    raw_value=raw_clean,
                    normalized_value=normalized,
                    canonical_value=matched.canonical_name,
                    canonical_entity_id=matched.canonical_entity_id,
                    decision=ResolutionDecision.ALIAS_MATCH,
                    match_method="ALIAS_EXACT_MATCH",
                    confidence=1.0,
                    evidence={
                        "alias_matched": normalized,
                        "matched_canonical_id": matched.canonical_entity_id
                    }
                )

        # ---------------------------------------------------------------------
        # Level 5: Composite Evidence Check (Combined independent signals)
        # ---------------------------------------------------------------------
        for rec in self.records:
            if rec.normalized_name in normalized or normalized in rec.normalized_name:
                # Disambiguation check for negative false merges:
                # E.g. 'Apple' vs 'Apple Records' or 'OpenAI' vs 'OpenAI Labs'
                words_raw = set(normalized.split())
                words_cand = set(rec.normalized_name.split())
                diff_words = words_raw.symmetric_difference(words_cand)
                
                distinguishing = {"labs", "research", "capital", "records", "systems", "technologies", "services", "web"}
                if diff_words.intersection(distinguishing):
                    # Separate distinct entities! Do NOT merge!
                    continue

                if norm_domain and any(d in norm_domain for d in rec.domains):
                    return ResolutionResult(
                        raw_value=raw_clean,
                        normalized_value=normalized,
                        canonical_value=rec.canonical_name,
                        canonical_entity_id=rec.canonical_entity_id,
                        decision=ResolutionDecision.COMPOSITE_MATCH,
                        match_method="COMPOSITE_EVIDENCE",
                        confidence=0.95,
                        evidence={
                            "name_overlap": True,
                            "domain_overlap": True,
                            "matched_canonical_id": rec.canonical_entity_id
                        }
                    )

        # ---------------------------------------------------------------------
        # New Canonical Entity Creation (When No Existing Canonical Matches)
        # Prevents false positive merges while assigning a stable ID for the new entity
        # ---------------------------------------------------------------------
        new_canonical_name = ' '.join(word.capitalize() for word in normalized.split()) if normalized else raw_clean
        new_canonical_id = generate_seed_entity_id(norm_type, new_canonical_name)

        return ResolutionResult(
            raw_value=raw_clean,
            normalized_value=normalized,
            canonical_value=new_canonical_name,
            canonical_entity_id=new_canonical_id,
            decision=ResolutionDecision.CREATE_NEW_CANONICAL,
            match_method="CREATE_NEW_CANONICAL_ENTITY",
            confidence=0.80,
            evidence={
                "existing_match_found": False,
                "created_new_canonical": True,
                "reason": "No existing canonical entity matched deterministic rules. Created new canonical record."
            }
        )

resolver = DeterministicEntityResolver()
