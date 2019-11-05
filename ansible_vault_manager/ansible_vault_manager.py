#!/usr/bin/env python

from __future__ import print_function, absolute_import
import os.path
import sys
import getpass
import argparse
import inspect
import fnmatch
from tempfile import gettempdir
from hashlib import md5
from importlib import import_module
from builtins import input
import glob

import yaml

PLUGIN_SEPARATOR = '%'
CLIENT_SEPARATOR = '@'

METADATA_FILE = '_metadata.yml'
METADATA_PLUGIN_KEY = 'plugin'
METADATA_ID_KEY = 'id'
METADATA_VAULT_FILES = 'files'

'''
Print message on stderr instead of stdout
'''


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def list_plugins():
    modules = glob.glob(os.path.join(os.path.dirname(__file__), 'keyring_plugins', '*.py'))
    return [os.path.basename(f)[:-3] for f in modules if os.path.isfile(f) and not f.endswith('__init__.py')]


def recursive_glob(rootdir='.', pattern='*'):
    '''
    Search recursively for files matching a specified pattern.

    Adapted from
    http://stackoverflow.com/questions/2186525/use-a-glob-to-find-files-recursively-in-python
    '''

    matches = []
    for root, dirnames, filenames in os.walk(rootdir):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(os.path.join(root, filename))

    return matches


def get_metadata(path, full_path=False, base_path=None):
    if not full_path:
        metadata_file = os.path.join(path, METADATA_FILE)
    else:
        if os.path.isabs(path):
            metadata_file = path
        else:
            metadata_file = os.path.join(base_path, path)
    if not os.path.exists(metadata_file):
        return {'vault_ids': []}

    with open(metadata_file, 'r') as stream:
        try:
            if 'FullLoader' in yaml.__dict__:
                vault_metadata = yaml.load(stream, Loader=yaml.FullLoader)
            else:
                vault_metadata = yaml.load(stream)
        except yaml.YAMLError as exc:
            eprint(exc)
            sys.exit(2)

    if 'include' in vault_metadata:
        for subfile in vault_metadata['include']:
            metadata = get_metadata(subfile, True, os.path.dirname(metadata_file))
            if 'vault_ids' in metadata:
                vault_metadata['vault_ids'] = vault_metadata['vault_ids'] + metadata['vault_ids']

    return vault_metadata


def write_metadata(metadata, path):
    with open(os.path.join(path, METADATA_FILE), 'w+') as stream:
        yaml.dump(metadata, stream)


def get_cached_password(vault_id):
    return False
    if os.path.isfile(os.path.join(gettempdir(), md5(vault_id.encode()).hexdigest())):
        with open(os.path.join(gettempdir(), md5(vault_id.encode()).hexdigest()), 'r') as cached:
            password = cached.read()
            return password

    return False


def set_cached_password(vault_id, password):
    with open(os.path.join(gettempdir(), md5(vault_id.encode()).hexdigest()), 'w+') as cached:
        password = cached.write(password)


def get_vault_lib():
    try:
        import ansible
        from ansible.parsing.vault import VaultLib
        _ansible_ver = float('.'.join(ansible.__version__.split('.')[:2]))
        if _ansible_ver < 2.5:
            eprint('This tool needs at least ansible 2.5 to works correctly')
            sys.exit(1)
    except ImportError:
        eprint('This tool needs at least ansible 2.5 to works correctly')
        sys.exit(1)

    return VaultLib


def _make_secrets(secret):
    secret = secret.encode('utf-8')

    from ansible.constants import DEFAULT_VAULT_ID_MATCH
    from ansible.parsing.vault import VaultSecret
    return [(DEFAULT_VAULT_ID_MATCH, VaultSecret(secret))]


def which(pgm):
    path = os.getenv('PATH')
    for p in path.split(os.path.pathsep):
        p = os.path.join(p, pgm)
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p


def set_default_subcommand():
    command_args = sys.argv[1:]
    known_subcommands = ['get-usable-ids', 'fetch', 'create']
    sub_command_defined = False
    for subcommand in known_subcommands:
        if subcommand in command_args:
            sub_command_defined = True
            break
    if not sub_command_defined and '-h' not in command_args and '--help' not in command_args:
        command_args = ['fetch'] + command_args
    return command_args


def parse_commandline():
    parser = argparse.ArgumentParser(
        description='Script to manage and fetch ansible-vault secrets',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(
        help='Desired action, default fetch',
        dest='action',
        metavar='action'
    )

    parser_usable = subparsers.add_parser(
        'get-usable-ids',
        description='Generate vault_id string from all usable configs in metadata',
        help='Generate vault_id string from all usable configs in metadata'
    )
    parser_usable.add_argument(
        '--vault-path',
        metavar='PATH',
        help='Diretory path where vault files are presents.',
        required=True
    )

    parser_fetch = subparsers.add_parser(
        'fetch',
        description='Fetch a password from remote keyring manager',
        help='Fetch a password from remote keyring manager'
    )
    parser_fetch.add_argument(
        '--vault-id',
        help='ID of key to fetch. Format: [plugin]%' + PLUGIN_SEPARATOR + '[id at plugin format].',
        required=True
    )

    parser_create = subparsers.add_parser(
        'create',
        description='Fetch a password from remote keyring manager',
        help='Fetch a password from remote keyring manager'
    )
    parser_create.add_argument(
        '--vault-path',
        metavar='PATH',
        help='Diretory path where vault files are presents.',
        required=True
    )
    parser_create.add_argument(
        '--plugin',
        help='Plugin name to use to store new password.',
        required=False
    )
    parser_create.add_argument(
        '--stdin-pwd',
        dest='stdin_pass',
        action='store_true',
        help='Password will be implicitly read from stdin.',
        required=False
    )
    parser_create.add_argument(
        '--plugin-param',
        dest='plugin_vars',
        action='append',
        help='Could be repeated, key=value param for plugin.',
        required=False
    )
    parser_create.add_argument(
        'file',
        metavar='FILE_PATH',
        help='File path to create.'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        default=False,
        help='Verbose mode for outputs'
    )

    args = parser.parse_args(set_default_subcommand())
    return parser, args


class HelpException(Exception):
    pass


class VaultManager:
    def __init__(self, args):
        self.args = args
        if self.args.action == 'fetch':
            self.fetch()
        elif self.args.action == 'get-usable-ids':
            self.get_usable_ids()
        elif self.args.action == 'create':
            self.create()
        elif self.args.action == 'rekey':
            self.not_ready()
        elif self.args.action == 'encrypt':
            self.not_ready()

    def fetch(self):
        vault_id = self.args.vault_id.split(PLUGIN_SEPARATOR, -1)
        password = self.fetch_password(vault_id[0], vault_id[1])
        print(password)

    def get_usable_ids(self):
        vault_metadata = get_metadata(self.args.vault_path)

        usable_ids = []
        # client_script is current script call path
        client_script = inspect.stack()[0][1]
        client_script = which('ansible-vault-manager-client')
        for id in vault_metadata['vault_ids']:
            try:
                password = self.fetch_password(id[METADATA_PLUGIN_KEY], id[METADATA_ID_KEY])
                if password:
                    usable_ids.append(
                        id[METADATA_PLUGIN_KEY]
                        + PLUGIN_SEPARATOR
                        + id[METADATA_ID_KEY]
                        + CLIENT_SEPARATOR
                        + client_script
                    )
            except Exception as e:
                if self.args.verbose:
                    eprint(e)

        if not usable_ids:
            sys.exit(0)

        print(','.join(usable_ids))

    def create(self):
        try:
            print('')
            new_file = self.args.file
            if new_file is None:
                new_file = input('File to create: ')
            if os.path.exists(os.path.join(self.args.vault_path, new_file)):
                eprint('This file already exists')
                sys.exit(2)

            plugin_name = self.args.plugin
            if plugin_name is None:
                plugin_name = input(
                    'Keyring plugin name to use [' + ', '.join(list_plugins()) + ']: '
                )
            plugin = self.get_plugin_instance(plugin_name)
            id = plugin.generate_id(self.args.plugin_vars)

            print('New ID to use: ' + id)
            print('')
            stdin_pass = self.args.stdin_pass
            if not stdin_pass and sys.stdin.isatty():
                password = getpass.getpass('New password: ')
                cpassword = getpass.getpass('Confirm password: ')

                if cpassword != password:
                    eprint('Passwords missmatch')
                    sys.exit(2)
            else:
                password = sys.stdin.read()

            password = password.strip()
            if password == '':
                print('Your password is empty !')
                sys.exit(2)
        except KeyboardInterrupt:
            print('')
            sys.exit(0)

        try:
            new_version = plugin.set_password(id, password)
            id = plugin.append_id_version(new_version)

            vault_metadata = get_metadata(self.args.vault_path)
            vault_metadata['vault_ids'].append(
                {
                    METADATA_ID_KEY: id,
                    METADATA_PLUGIN_KEY: plugin_name,
                    METADATA_VAULT_FILES: [new_file]
                }
            )
            write_metadata(vault_metadata, self.args.vault_path)

            VaultLib = get_vault_lib()
            vault_api = VaultLib(_make_secrets(password))
            with open(os.path.join(self.args.vault_path, new_file), 'w') as stream:
                encrypted = vault_api.encrypt('---')
                stream.write(encrypted)
        except Exception as e:
            eprint(e)
            sys.exit(2)
            if (self.args.verbose):
                import traceback
                traceback.print_exc()

    def not_ready(self):
        print("Action not yet ready !!!")
        sys.exit(2)

    def fetch_password(self, vault_plugin, vault_id):
        if get_cached_password(vault_id):
            return (0, get_cached_password(vault_id), "")
        else:
            plugin = self.get_plugin_instance(vault_plugin)
            return plugin.fetch(vault_id)

    def get_plugin_instance(self, plugin_name):
        if __name__ == '__main__':
            module_path = 'keyring_plugins.' + plugin_name
            package = None
        else:
            module_path = '.keyring_plugins.' + plugin_name
            package = ('.').join(__name__.split('.')[:-1])
        if self.args.verbose:
            print('Import module : ' + module_path)

        try:
            module = import_module(module_path, package)
            KeyringPlugin = module.KeyringPlugin
        except ImportError as e:
            if self.args.verbose:
                print(e)
            eprint('Keyring manager client plugin ' + plugin_name + ' not found')

        return KeyringPlugin()


def main():
    parser, args = parse_commandline()
    try:
        VaultManager(args)
    except HelpException as e:
        print(e.message)
        parser.print_help()


if __name__ == '__main__':
    main()
