"""Compose the approved appendix without modifying the GD2 baseline."""
from copy import deepcopy

ROLES = {
    '/v1/swaps/{swap_id}/recovery': ['ADMIN', 'TECHNICIAN'],
    '/v1/swaps/{swap_id}/recovery/evidence': ['TECHNICIAN'],
    '/v1/swaps/{swap_id}/recovery/confirmations': ['CUSTOMER'],
    '/v1/swaps/{swap_id}/recovery/settle': ['TECHNICIAN'],
    '/v1/device/recovery-tasks': ['DEVICE'],
    '/v1/device/recovery-observations': ['DEVICE'],
}


def apply_appendix(spec, generated):
    # Never replace existing Phase1-7 schemas with FastAPI's inferred schemas.
    names = {'LegacyEvidence', 'StructuredEvidence', 'LegacySettlement', 'StructuredSettlement',
             'BeginOperation', 'TechnicianAttest', 'AttachOperation', 'CustomerConfirmation',
             'DeviceObservation', 'ServiceObservation', 'RecoveryTasks', 'RecoveryTask',
             'RecoveryContext', 'RecoveryCommandContext', 'RecoveryConfirmationReceipt',
             'RecoveryObservationReceipt', 'InspectionTask', 'PreActionInspection',
             'InspectionSlot', 'InspectionPresenter', 'InspectionCommand', 'InspectionService',
             'AuthorizeAction', 'AuthorizationAcknowledgment', 'AuthorizationIntentTask', 'ActionTask', 'PostActionReceipt'}
    names.update({'ReinspectOperation','CloseNoEffect','ReconciliationTask','ClosureTask','NoEffectClosure','ReconciliationInspection'})
    spec['components']['schemas'].update({name: deepcopy(schema)
        for name, schema in generated.get('components', {}).get('schemas', {}).items() if name in names})
    errors = deepcopy(spec['paths']['/v1/swaps/{swap_id}/recovery']['get']['responses'])
    errors.pop('200', None)
    for path, roles in ROLES.items():
        if path not in generated['paths']:
            continue
        methods = deepcopy(generated['paths'][path])
        for method, operation in methods.items():
            baseline = spec['paths'].get(path, {}).get(method)
            if baseline:
                # Keep existing operation identity, errors, authorization
                # metadata and response; use the explicit approved input union.
                merged = deepcopy(baseline)
                if 'requestBody' in operation:
                    merged['requestBody'] = operation['requestBody']
                methods[method] = merged
            else:
                operation.update({'x-roles': roles, 'x-fr': ['FR12'],
                    'security': [{'DeviceKey' if roles == ['DEVICE'] else 'UserBearer': []}],
                    'x-contract-version': 'P8-REC-0.1'})
                operation['responses'].pop('422', None)
                operation['responses'].update(deepcopy(errors))
        spec['paths'][path] = methods
    case = spec['components']['schemas']['RecoveryCases']
    case['properties']['operation_id'] = {'type': ['string', 'null'], 'format': 'uuid'}
    from app.api.recovery_schemas import RecoveryConfirmationContext, RecoveryOperationView
    operation_schema = RecoveryOperationView.model_json_schema(ref_template='#/components/schemas/{model}')
    spec['components']['schemas'].update(operation_schema.pop('$defs', {}))
    spec['components']['schemas']['RecoveryOperationView'] = operation_schema
    case['properties']['active_operation'] = {
        'anyOf': [{'$ref': '#/components/schemas/RecoveryOperationView'}, {'type': 'null'}]}
    spec['components']['schemas']['RecoveryConfirmationContext'] = RecoveryConfirmationContext.model_json_schema()
    spec['components']['schemas']['RecoveryConfirmationContext']['x-contract-version'] = 'P8-REC-0.2/customer-projection-1'
    spec['components']['schemas']['SwapTransactions']['properties']['recovery_confirmation'] = {
        'anyOf': [{'$ref': '#/components/schemas/RecoveryConfirmationContext'}, {'type': 'null'}]}

    # B1b: union only the frozen 0.3 branch. No provider/callback extension here.
    import yaml
    from app.config import ROOT
    overlay = yaml.safe_load((ROOT/'docs/implementation-contracts/P8-REC-0.3/openapi.overlay.yaml')
                             .read_text(encoding='utf-8-sig'))
    spec['components']['schemas'].update({name: deepcopy(schema)
        for name, schema in overlay['components']['schemas'].items() if name.startswith('P8ND')})
    spec['components']['schemas']['P8NDCompatibleTasks'] = deepcopy(
        generated['components']['schemas']['P8NDCompatibleTasks'])
    for path, methods in overlay['paths'].items():
        for method, addition in methods.items():
            current = spec['paths'][path][method]
            if current['security'] != addition['security'] or current['operationId'] != addition['operationId']:
                raise ValueError('Frozen no-delivery operation/security mismatch')
            # Generated request bodies already contain old + exact 0.3 DTO refs.
            # Recovery GET/evidence responses must also admit the new view.
            if path.endswith('/recovery') or path.endswith('/recovery/evidence'):
                response = current['responses']['200']['content']['application/json']
                response['schema'] = {'anyOf': [deepcopy(response['schema']),
                    {'$ref': '#/components/schemas/P8NDNoDeliveryResponse'}]}
    projection = spec['components']['schemas']['SwapTransactions']['properties']['recovery_confirmation']
    spec['components']['schemas']['SwapTransactions']['properties']['recovery_confirmation'] = {
        'anyOf': [deepcopy(projection), {'$ref': '#/components/schemas/P8NDCustomerProjection'}]}
