#!/usr/bin/env python

from __future__ import print_function
import os.path
from hashlib import md5
from builtins import input
from tempfile import gettempdir
import uuid

try:
    import boto3
except ImportError as e:
    raise RuntimeError('You need to install boto3 python lib to use this plugin')

from . import BaseKeyringPlugin

CONFIG_SEPARATOR = ':'


def get_cached_password(vault_id):
    if (os.path.isfile(os.path.join(gettempdir(), md5(vault_id.encode()).hexdigest()))):
        with open(os.path.join(gettempdir(), md5(vault_id.encode()).hexdigest()), 'r') as cached:
            password = cached.read()
            return password

    return False


def set_cached_password(vault_id, password):
    with open(os.path.join(gettempdir(), md5(vault_id.encode()).hexdigest()), 'w+') as cached:
        password = cached.write(password)


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

        if asked_version is None:
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
            filtered_iterator = page_iterator.search(
                "Parameters[?Version==`" + asked_version + "`]"
            )
            value = None
            for key_data in filtered_iterator:
                value = key_data['Value']

        if (value is None):
            raise Exception('Parameter not found on SSM')

        set_cached_password(id, value)

    return value


class KeyringPlugin(BaseKeyringPlugin):

    def parse_vault_id(self, vault_id):
        vault_id = vault_id.split(CONFIG_SEPARATOR)
        account = vault_id[0]
        region = vault_id[1]
        ssm_key = vault_id[2]
        asked_version = None
        if len(vault_id) > 3:
            asked_version = vault_id[3]

        return (account, region, ssm_key, asked_version)

    def fetch(self, vault_id):
        account, region, ssm_key, asked_version = self.parse_vault_id(vault_id)
        return get_ssm_parameter(account, region, ssm_key, asked_version)

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

    def generate_id(self, plugin_vars=None):
        params = {}
        if plugin_vars is not None:
            params = self.parse_plugin_vars(plugin_vars)

        if 'profile' not in params:
            aws_account = input('AWS Account profile: ')
        else:
            aws_account = params['profile']
        if 'region' not in params:
            aws_region = input('AWS Region: ')
        else:
            aws_region = params['region']
        if 'path' not in params:
            aws_scope = input('Secret base path (ex. /ansible/dev/): ')
        else:
            aws_scope = params['path']
        if (not aws_scope.endswith('/')):
            aws_scope = aws_scope + '/'
        self.id = CONFIG_SEPARATOR.join([aws_account, aws_region, aws_scope + str(uuid.uuid4())])
        return self.id

    def append_id_version(self, new_version):
        return self.id + ('' if new_version is None else CONFIG_SEPARATOR + str(new_version))
