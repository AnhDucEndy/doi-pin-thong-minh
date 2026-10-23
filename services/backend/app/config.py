from dataclasses import dataclass
from pathlib import Path
import os
import re

from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
import json
import yaml

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / '.env', override=False)


class ConfigNotReady(ValueError):
    pass


def approved_policy(path=None):
    source = Path(path) if path else ROOT / 'doi-pin-giai-doan-2/contracts/demo-config.approved.yaml'
    schema = json.loads((ROOT / 'doi-pin-giai-doan-2/contracts/demo-config.schema.json').read_text(encoding='utf-8-sig'))
    try:
        data = yaml.safe_load(source.read_text(encoding='utf-8-sig'))
        Draft202012Validator(schema).validate(data)
        if any(data.get(k) is None for k in ('fee_minor', 'soc_min_pct', 'temperature_max_c')):
            raise ValueError('Required policy value is missing')
        if data['decision_status'] != 'APPROVED_FOR_SIMULATION_BY_USER':
            raise ValueError('Policy is not approved for simulation')
        if (data['station_count'], data['compartments_per_station'], data['fee_minor'], data['soc_min_pct'],
            data['soh_min_pct'], data['temperature_max_c'], data['battery_family']) != (2, 6, 9000, 80, 80, 40, 'DEMO_FAMILY_A'):
            raise ValueError('Policy differs from approved MVP')
        return data
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, ValidationError) as error:
        # Expose only a stable code through the API; never config/secret content.
        raise ConfigNotReady('CONFIG_NOT_READY') from error


@dataclass(frozen=True)
class Settings:
    database_url: str
    schema: str = 'doi_pin'
    policy_path: str | None = None

    def __post_init__(self):
        if not self.database_url.startswith('postgresql+psycopg://'):
            raise ValueError('PostgreSQL with psycopg is required')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', self.schema):
            raise ValueError('Invalid database schema')

    @classmethod
    def from_env(cls):
        return cls(os.environ['DATABASE_URL'], os.getenv('DATABASE_SCHEMA', 'doi_pin'))
