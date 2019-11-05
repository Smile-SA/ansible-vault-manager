from __future__ import (absolute_import, division, print_function)
import uuid

__all__ = ["BaseKeyringPlugin"]


class BaseKeyringPlugin:
    verbose = False

    def __init__(self, verbose=True):
        self.verbose = verbose

    def generate_id(self, plugin_vars=None):
        self.id = str(uuid.uuid4())
        return self.id

    def append_id_version(self, new_version):
        return self.id

    def parse_plugin_vars(self, vars):
        params = {}
        for couple in vars:
            (key, value) = couple.split('=', 1)
            params[key] = value

        return params

    def parse_vault_id(self, vault_id):
        pass

    def fetch(self, vault_id):
        pass

    def set_password(self, id, password):
        pass
