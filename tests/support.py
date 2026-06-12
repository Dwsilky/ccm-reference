"""Minimal fakes for states moto can't represent (see ADR-002).

Example: moto has no way to attach access keys to the root account, so the
root_access_keys NON_COMPLIANT path is exercised with a faked
GetAccountSummary response instead. The handler only ever calls
`session.client(name)`, so a dict-backed fake session is sufficient.
"""


class FakeSession:
    def __init__(self, **clients):
        self._clients = clients

    def client(self, name, **kwargs):
        return self._clients[name]


class FakeSTS:
    def get_caller_identity(self):
        return {"Account": "123456789012"}
