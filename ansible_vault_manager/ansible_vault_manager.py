#!/usr/bin/env python

from __future__ import print_function
import yaml
import inspect
import os.path
import argparse
import sys
import getpass
import fnmatch
import subprocess
from hashlib import md5
from importlib import import_module
from builtins import input

PLUGIN_SEPARATOR = '%'
CLIENT_SEPARATOR = '@'

METADATA_FILE = '_metadata.yml'
METADATA_PLUGIN_KEY = 'client'
METADATA_ID_KEY = 'id'
METADATA_VAULT_FILES = 'files'

'''
Print message on stderr instead of stdout
'''
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def list_plugins():
    return ['aws_ssm','bitwarden']

def recursive_glob(rootdir='.', pattern='*'):
	"""Search recursively for files matching a specified pattern.

	Adapted from http://stackoverflow.com/questions/2186525/use-a-glob-to-find-files-recursively-in-python
	"""

	matches = []
	for root, dirnames, filenames in os.walk(rootdir):
	  for filename in fnmatch.filter(filenames, pattern):
		  matches.append(os.path.join(root, filename))

	return matches

def get_metadata(path):
    metadata_file = path + "/" + METADATA_FILE
    if not os.path.exists(metadata_file):
        return {'vault_ids': []}

    with open(metadata_file, 'r') as stream:
        try:
            vault_metadata = yaml.load(stream)
            stream.close()
        except yaml.YAMLError as exc:
            eprint(exc)
            sys.exit(2)

    return vault_metadata

def write_metadata(metadata, path):
    with open(path + "/" + METADATA_FILE, 'w+') as stream:
        yaml.dump(metadata, stream)
        stream.close()

def get_cached_password(vault_id):
    return False
    if (os.path.isfile('/tmp/' + md5(vault_id.encode()).hexdigest())):
        with open('/tmp/' + md5(vault_id.encode()).hexdigest(), 'r') as cached:
            password = cached.read()
            cached.close()
            return password

    return False

def set_cached_password(vault_id, password):
    with open('/tmp/' + md5(vault_id.encode()).hexdigest(), 'w+') as cached:
        password = cached.write(password)
        cached.close()

def fetch_password(vault_client, vault_id):
    if get_cached_password(vault_id):
        return (0, get_cached_password(vault_id), "")
    else:
        plugin = get_plugin_instance(vault_client)
        current_password = plugin.fetch(vault_id)
        return current_password

def get_plugin_instance(plugin_name):
    try:
        if (args.verbose):
            print('Import module : keyring_plugins.' + plugin_name)

        if (__package__ == None):
            module = import_module('keyring_plugins.' + plugin_name)
        else:
            module = import_module('.keyring_plugins.' + plugin_name, __package__)
        KeyringPlugin = module.KeyringPlugin
    except ImportError as e:
        if (args.verbose):
            print(e)
        eprint('Smile keyring manager client plugin ' + plugin_name + ' not found')

    return KeyringPlugin()

parser = argparse.ArgumentParser(
    description='Script to manage and fetch ansible-vault secrets',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('--action', default='fetch', choices=['fetch','rekey','encrypt','encrypt_string','get-usable-ids','create'], help='Action to do.', required=False)
parser.add_argument('--vault-id', help='ID of key to fetch. Format: [plugin]%' + PLUGIN_SEPARATOR + '[id at plugin format].', required=False)
parser.add_argument('--vault-path', metavar='PATH', help='Diretory path where vault files are presents.', required=False)
parser.add_argument('--verbose', '-v', action='store_true', default=False, help='Verbose mode for outputs')
args = parser.parse_args()

if args.action != 'fetch':
    import ansible
    try:
        from ansible.parsing.vault import VaultLib
    except ImportError:
        # Ansible<2.0
        from ansible.utils.vault import VaultLib

    def _make_secrets(secret):
        secret = secret.encode('utf-8')
        _ansible_ver = float('.'.join(ansible.__version__.split('.')[:2]))
        if _ansible_ver < 2.4:
            return secret

        from ansible.constants import DEFAULT_VAULT_ID_MATCH
        from ansible.parsing.vault import VaultSecret
        return [(DEFAULT_VAULT_ID_MATCH, VaultSecret(secret))]

if args.action == 'fetch':
    if args.vault_id == None:
        eprint('vault-id is mandatory for fetch action\n')
        parser.print_help(sys.stderr)
        sys.exit(2)

    vault_id = args.vault_id.split(PLUGIN_SEPARATOR, -1)
    password = fetch_password(vault_id[0], vault_id[1])
    print(password)

elif args.action == 'get-usable-ids':
    if args.vault_path == None:
        eprint('vault-path is mandatory to check usable ids\n')
        parser.print_help(sys.stderr)
        sys.exit(2)

    vault_metadata = get_metadata(args.vault_path)

    usable_ids = []
    # client_script is current script call path
    client_script = inspect.stack()[0][1]
    for id in vault_metadata['vault_ids']:
        try:
            password = fetch_password(id[METADATA_PLUGIN_KEY], id[METADATA_ID_KEY])
            if (password):
                usable_ids.append(id[METADATA_PLUGIN_KEY] + PLUGIN_SEPARATOR + id[METADATA_ID_KEY] + CLIENT_SEPARATOR + client_script)
            elif (args.verbose):
                print(errs)
        except Exception as e:
            if (args.verbose):
                eprint(e)

    if (len(usable_ids) == 0):
        sys.exit(0)

    print(','.join(usable_ids))

elif args.action == 'rekey':
    print("Action not yet ready !!!")
    sys.exit(2)

elif args.action == 'create':
    if args.vault_path == None:
        eprint('vault-path is mandatory to encrypt dir content\n')
        parser.print_help(sys.stderr)
        sys.exit(2)

    try:
        print('')
        new_file = input('File to create: ')
        if os.path.exists(args.vault_path + '/' + new_file):
            eprint('This file already exists')
            sys.exit(2)
        plugin_name = input('Keyring plugin name to use [' + ', '.join(list_plugins()) + ']: ')
        plugin = get_plugin_instance(plugin_name)
        id = plugin.generate_id()
        print('New ID to use: ' + id)
        print('')
        password = getpass.getpass('New password: ')
        cpassword = getpass.getpass('Confirm password: ')
    except KeyboardInterrupt:
        print('')
        sys.exit(0)

    if cpassword != password:
        eprint('Passwords missmatch')
        sys.exit(2)

    new_version = plugin.set_password(id, password)
    id = plugin.append_id_version(new_version)

    vault_metadata = get_metadata(args.vault_path)
    vault_metadata['vault_ids'].append(
        {METADATA_ID_KEY: id, METADATA_PLUGIN_KEY: plugin_name, METADATA_VAULT_FILES: [new_file]}
    )
    write_metadata(vault_metadata, args.vault_path)

    vault_api = VaultLib(_make_secrets(password))
    with open(args.vault_path + '/' + new_file, 'w') as stream:
        encrypted = vault_api.encrypt('---')
        stream.write(encrypted)
        stream.close()


elif args.action == 'encrypt':
    print("Action not yet ready !!!")
    sys.exit(2)
