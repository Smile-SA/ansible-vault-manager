from __future__ import (absolute_import, division, print_function)
__all__ = ["BaseKeyringPlugin"]

import uuid

class BaseKeyringPlugin:
    verbose = False

    def __init__(self, verbose=True):
        self.verbose = verbose

    def generate_id(self):
        self.id = str(uuid.uuid4())
        return self.id

    def append_id_version(self, new_version):
        return self.id

    def parse_vault_id(self, vault_id):
        pass

    def fetch(self, vault_id):
        pass

    def set_password(self, id, password):
        pass