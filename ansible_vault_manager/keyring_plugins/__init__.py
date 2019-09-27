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
