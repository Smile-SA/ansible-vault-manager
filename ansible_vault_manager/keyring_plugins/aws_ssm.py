#!/usr/bin/env python

from __future__ import print_function
import yaml
import os.path
import argparse
try:
  import boto3
except ImportError as e:
  raise RuntimeError('You need to install boto3 python lib to use this plugin')
import sys
import getpass
import fnmatch
from hashlib import md5
from builtins import input
import uuid
from keyring_plugins import BaseKeyringPlugin

CONFIG_SEPARATOR = ':'

def get_cached_password(vault_id):
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

def get_ssm_client(account, region):
    boto3.setup_default_session(
        profile_name=account,
        region_name=region
    )

    return boto3.client('ssm')

def get_ssm_parameter(account, region, ssm_key, asked_version=None):
    id = account + region + ssm_key + str(asked_version)
    if get_cached_password(id):
        value = get_cached_password(id)
    else:
        ssm = get_ssm_client(account, region)

        if asked_version == None:
            response = ssm.get_parameter(
                Name=ssm_key,
                WithDecryption=True
            )
            value = response['Parameter']['Value']
        else:
            paginator = ssm.get_paginator('get_parameter_history')
            page_iterator = paginator.paginate(
                Name=ssm_key,
                WithDecryption=True
            )
            filtered_iterator = page_iterator.search("Parameters[?Version==`" + asked_version + "`]")
            value = None
            for key_data in filtered_iterator:
                value = key_data['Value']

        if (value == None):
            raise Exception('Parameter not found on SSM')

        set_cached_password(id, value)

    return value

class KeyringPlugin(BaseKeyringPlugin):

    def parse_vault_id(self, vault_id):
        vault_id = vault_id.split(CONFIG_SEPARATOR)
        account=vault_id[0]
        region=vault_id[1]
        ssm_key=vault_id[2]
        asked_version=None
        if len(vault_id) > 3:
            asked_version=vault_id[3]

        return (account, region, ssm_key, asked_version)

    def fetch(self, vault_id):
        account, region, ssm_key, asked_version = self.parse_vault_id(vault_id)
        return get_ssm_parameter(account, region, ssm_key, asked_version)

    def change_password(self, vault_id, vault_path):
        account, region, ssm_key, asked_version = self.parse_vault_id(vault_id)

        if vault_path == None:
            eprint('vault-path is mandatory to change password\n')
            parser.print_help(sys.stderr)
            sys.exit(2)

        text = '''
        Be very carefull ! Change passwords of vault files could causes deploying/self-provisioning
        issues if Git is not aligned with AWS.
        Use a strong password to avoid bruteforces attacks.

        This action will do :
        * ansible-vault rekey <vault file> with new password
        * Push password on AWS Parameter Store to a new version
        * Write version number in local `vault_vars/_metadata.yml`

        Then you have to :
        * Commit all changed files in `vault_vars/`
        * Ensure `vault_vars/_metadata.yml` is always attached to vault files with same version
        This version is about Parameter Store history and avoid issues in env for exemple if you change
        password now and a self-provisioning start at the same time in production branch (where you not
        pushed new vaults) for exemple

        If you are not ready... CTRL-c !

        '''
        print(text)
        try:
            files = recursive_glob(vault_path)
            vault_files = []
            print('Files bellow will be affected :')
            for file in files:
                if (os.stat(file).st_size > 0 and not os.path.islink(file) and os.path.basename(file) != '_metadata.yml'):
                    vault_files.append(file)
                    print(file)

            print('')
            if (sys.stdin == ""):
                password = getpass.getpass('New password: ')
                cpassword = getpass.getpass('Confirm password: ')
            else:
                password = sys.stdin
                input("Press Enter to continue...")
        except KeyboardInterrupt:
            print('')
            sys.exit(0)
        if cpassword != password:
            eprint('Passwords missmatch')
            sys.exit(2)

        with open(vault_path + "/_metadata.yml", 'r') as stream:
            vault_metadata = yaml.load(stream)
            stream.close()

        for id in vault_metadata['vault_ids']:
            account_tmp, region_tmp, ssm_key_tmp, asked_version_tmp = self.parse_vault_id(id['id'])
            if (account_tmp == account and region_tmp == region and ssm_key_tmp == ssm_key):
                asked_version = asked_version_tmp

        password_ssm = get_ssm_parameter(account, region, ssm_key, asked_version)

        old_vault_api = VaultLib(_make_secrets(password_ssm))
        vault_api = VaultLib(_make_secrets(password))
        for file in vault_files:
            try:
                if not vault_api.is_encrypted_file(file):
                    print('Skip non vault file ' + file)
                    continue
                #rekey
                with open(file, 'r+') as stream:
                    old_encrypted = stream.read()
                    stream.seek(0)
                    vars = old_vault_api.decrypt(old_encrypted)
                    encrypted = vault_api.encrypt(vars)
                    stream.write(encrypted)
                    stream.close()

            except ansible.errors.AnsibleError as e:
                eprint('ERROR with file ' + file)
                eprint(e)
                sys.exit(2)

        response = ssm.put_parameter(
            Name=ssm_key,
            Overwrite=True,
            Type='SecureString',
            Value=password
        )
        new_version = str(response['Version'])
        print('New version ' + new_version + ' pushed on SSM')

        # Write new version in vault metadata
        for i, id in enumerate(vault_metadata['vault_ids']):
            account_tmp, region_tmp, ssm_key_tmp, asked_version_tmp = self.parse_vault_id(id['id'])
            if (account_tmp == account and region_tmp == region and ssm_key_tmp == ssm_key):
                vault_metadata['vault_ids'][i]['id'] = current_env + ':' + ssm_key + ':' + new_version

        with open(vault_path + "/_metadata.yml", 'w') as stream:
            yaml.dump(vault_metadata, stream)
            stream.close()

    def encrypt(self, vault_id, vault_path):
        account, region, ssm_key, asked_version = self.parse_vault_id(vault_id)
        if vault_path == None:
            eprint('vault-path is mandatory to encrypt dir content\n')
            parser.print_help(sys.stderr)
            sys.exit(2)

        ssm = get_ssm_client(account, region)
        response = ssm.get_parameter(
            Name=ssm_key,
            WithDecryption=True
        )

        vault_api = VaultLib(_make_secrets(response['Parameter']['Value']))
        files = recursive_glob(vault_path)
        non_vault_files = []
        print('Files bellow will be affected :')
        for file in files:
            if os.stat(file).st_size > 0 and not os.path.islink(file) and os.path.basename(file) != '_metadata.yml':
                if not vault_api.is_encrypted_file(file):
                    non_vault_files.append(file)
                    print(file)

        for file in non_vault_files:
            with open(file, 'r+') as stream:
                vars = stream.read()
                stream.seek(0)
                encrypted = vault_api.encrypt(vars)
                stream.write(encrypted)
                stream.close()

    def set_password(self, id, password):
        account, region, ssm_key, asked_version = self.parse_vault_id(id)

        ssm = get_ssm_client(account, region)
        response = ssm.put_parameter(
            Name=ssm_key,
            Overwrite=True,
            Type='SecureString',
            Value=password
        )
        new_version = str(response['Version'])
        return new_version

    def generate_id(self):
        aws_account = input('AWS Account profile: ')
        aws_region = input('AWS Region: ')
        aws_scope = input('Secret base path (ex. /ansible/dev/): ')
        self.id = CONFIG_SEPARATOR.join([aws_account, aws_region, aws_scope + str(uuid.uuid4())])
        return self.id

    def append_id_version(self, new_version):
        return self.id + ('' if new_version == None else CONFIG_SEPARATOR + str(new_version))
