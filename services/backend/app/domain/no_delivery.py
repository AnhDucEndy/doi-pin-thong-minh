"""Canonical readonly history shared by the two independently loaded stores.

These formatters confer no eligibility. The Backend must additionally compare
the complete command/service/source inventory and current authenticated proof.
"""
from app.domain.recovery import canonical_hash


def history_digest(ledger_id, swap_id, serial, events, command_digest, service_digest):
    return canonical_hash({'ledger_id': str(ledger_id), 'swap_id': str(swap_id),
        'serial': serial, 'events': [
            {'event_id': str(e['event_id']), 'hash': e['payload_hash'],
             'boot_id': str(e['boot_id']), 'seq': e['seq']} for e in events],
        'command_digest': command_digest, 'service_digest': service_digest})


def journal_digest(previous, table, identity, body):
    return canonical_hash({'previous': previous, 'table': table,
                           'identity': str(identity), 'body': body})
