"""Compile reviewed S1 candidates against actual router source, never authorize.

An exact syntactically valid route is insufficient: future S1 fixture identities,
request DTO/action and source checkpoint must be separately admitted.
"""
import ast
import hashlib
from pathlib import Path
from uuid import UUID

from .adapter import require

S1_TEMPLATES=(
    ('GET','/health'),('POST','/v1/auth/login'),
    ('GET','/v1/swaps/{swap_id}'),('GET','/v1/swaps/{swap_id}/recovery'),
    ('POST','/v1/swaps/{swap_id}/recovery/evidence'),
    ('POST','/v1/swaps/{swap_id}/recovery/confirmations'),
    ('POST','/v1/swaps/{swap_id}/recovery/settle'),
    ('POST','/v1/payments/{payment_id}/refund'),
    ('GET','/v1/device/commands'),('GET','/v1/device/recovery-tasks'),
    ('POST','/v1/device/events'),('POST','/v1/device/recovery-observations'),
    ('POST','/v1/device/verifications'),('POST','/v1/qr-challenges'),
    ('POST','/v1/swaps/{swap_id}/reserve'),('POST','/v1/swaps/{swap_id}/consent'),
)


def compile_candidates(root,swap_id,payment_id):
    bindings=dict(swap_id=str(UUID(str(swap_id))),payment_id=str(UUID(str(payment_id))))
    root=Path(root);found={}
    for path in [root/'services/backend/app/main.py',*sorted((root/'services/backend/app/api').glob('*.py'))]:
        source=path.read_bytes()
        for node in ast.walk(ast.parse(source.decode('utf-8-sig'))):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            for d in node.decorator_list:
                if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ('get','post','put','patch') and d.args and isinstance(d.args[0],ast.Constant):
                    key=(d.func.attr.upper(),d.args[0].value)
                    if key in S1_TEMPLATES:
                        require(key not in found,'DUPLICATE_ROUTE_SOURCE')
                        found[key]=dict(source=str(path.relative_to(root)),line=d.lineno,sha256=hashlib.sha256(source).hexdigest())
    require(set(found)==set(S1_TEMPLATES),'S1_ROUTE_SOURCE_DRIFT')
    return [dict(method=m,path=p.format(**bindings),template=p,source=found[(m,p)],
                 authorized=False,reason='S1_NOT_APPROVED_AND_ENTITY_BINDING_NOT_YET_ADMITTED') for m,p in S1_TEMPLATES]
