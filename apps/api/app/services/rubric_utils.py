import json
from hashlib import sha256
from typing import Any


def rubric_payload_hash(version: Any) -> str:
    payload = {
        "criteria": version.criteria,
        "engine_mapping": version.engine_mapping,
        "source_jd_document_id": version.source_jd_document_id,
        "source_jd_sha256": version.source_jd_sha256,
        "structured_jd_payload": version.structured_jd_payload,
        "version_number": version.version_number,
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
