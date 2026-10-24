"""The approved DeviceEvent union, validated without extending its JSON schema."""
from functools import lru_cache
from datetime import datetime
import hashlib
import json

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry
from referencing.jsonschema import DRAFT202012
from pydantic import ValidationError as ModelError
import yaml

from app.config import ROOT
from app.domain.bms import BMSPayload
from app.application.identity import DomainError


@lru_cache
def validator():
    spec = yaml.safe_load((ROOT/'doi-pin-giai-doan-2/contracts/openapi.yaml').read_text(encoding='utf-8-sig'))
    registry = Registry().with_resource('urn:device-contract', DRAFT202012.create_resource(spec))
    return Draft202012Validator({'$ref':'urn:device-contract#/components/schemas/DeviceEvent'},
        registry=registry, format_checker=FormatChecker())


def validate_event(body):
    try:
        validator().validate(body)
        if body['kind'] == 'TELEMETRY':
            BMSPayload.model_validate(body['payload'])
        observed = datetime.fromisoformat(body['observed_at'].replace('Z','+00:00'))
        if observed.tzinfo is None:
            raise ValueError()
        digest = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        return observed, digest
    except (ValidationError, ModelError, ValueError, TypeError, KeyError) as error:
        raise DomainError(422,'DEVICE_EVENT_INVALID') from error
