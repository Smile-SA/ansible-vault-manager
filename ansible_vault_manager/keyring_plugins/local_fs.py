from __future__ import print_function
import os.path
from builtins import input
import uuid

from . import BaseKeyringPlugin, KeyringException

CONFIG_SEPARATOR = ':'

'''
Vault ID format : 
[basepath]:[file]:[version]
'''


class KeyringPlugin(BaseKeyringPlugin):
    def append_id_version(self, new_version):
        return self.id + ('' if new_version is None else CONFIG_SEPARATOR + str(new_version))

    def generate_id(self, plugin_vars=None):
        params = {}
        if plugin_vars is not None:
            params = self.parse_plugin_vars(plugin_vars)

        if 'basepath' not in params:
            basepath = input('Base path (ex. /mnt/secrets/myproject/): ')
        else:
            basepath = params['path']
        
        self.id = CONFIG_SEPARATOR.join([basepath, str(uuid.uuid4())])
        return self.id

    def parse_vault_id(self, vault_id):
        vault_id = vault_id.split(CONFIG_SEPARATOR)
        basepath = vault_id[0]
        filename = vault_id[1]
        asked_version = None
        if len(vault_id) > 2:
            asked_version = vault_id[2]

        return (basepath, filename, asked_version)

    def fetch(self, vault_id):
        basepath, filename, asked_version = self.parse_vault_id(vault_id)
        if asked_version is None:
            asked_version = 1
        filepath = os.path.join(basepath, filename + '.' + str(asked_version))
        with open(filepath, 'r') as file:
            password = file.read()
        
        return password

    def set_password(self, id, password):
        basepath, filename, asked_version = self.parse_vault_id(id)

        if asked_version is None:
            new_version = 1
        else:
            new_version = asked_version + 1
        
        new_filepath = os.path.join(basepath, filename + '.' + str(new_version))
        if os.path.exists(new_filepath):
            raise KeyringException(
                "You can't override an existing version ({0}) ! Remove it or increment version before.".format(new_filepath)
            )

        with open(new_filepath, 'w') as file:
            file.write(password)

        return new_version