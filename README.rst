Introduction:
=============

This tool is a manager to make easier and sharable ansible-vault integration.
It's almost a prerequisite to combine ansible-vault and CI/CD.
With it you don't need anymore to share vault passphrase with other people.
You can rotate them transparently for security good practices.
You can use "keyring plugins" to extend it and store passphrases on AWS SSM,
Bitwarden, or other secured storage system.

Help :
======

::

    ansible-vault-manager-client --help

Important note :
================

The name of executable ends with `-client` for a specific reason !
Since ansible 2.5 ansible vault cares about this
suffix, so it's very important to keep it !

Examples :
==========

Create a new vaulted file :

::

    ansible-vault-manager-client create --vault-path <dir where create new file>

It will ask you for filename, keyring plugin, keyring plugin options,
and encryption password

Automatic integration :

Before run any ansible command (like `ansible-playbook`) you have to
declare your identities list :

::

    # Check usable vault ids and add them to ansible env var
    USABLE_IDS=$(ansible-vault-manager-client get-usable-ids --vault-path "provisioning/inventory/vault_vars/")
    echo $USABLE_IDS
    if [ "$USABLE_IDS" != "" ]; then
        export ANSIBLE_VAULT_IDENTITY_LIST="$USABLE_IDS"
    fi


TODO :
======

* Make extensible via custom deported plugins added via a "plugin path"
* Make native plugin Hashi Vault
* Make native plugin S3
* Make native plugin MultiPass
* Make native plugin sshfs

Good practices :
================

In any playbook, you can add this play to include all vaulted vars, ordered
by ansible groups logic
You can create a non standard "vault_vars" dir in your inventory dir.
All files into, matching to hosts groups, will be included.
"with_fileglob" permit to not fail if file not exists.

::

    - hosts:
        - all
      connection: local
      tasks:
        - name: Include vaulted vars
            include_vars: "{{ item }}"
            with_fileglob: "{{ group_names | map('regex_replace', '^(.*)$', 'inventory/vault_vars/\\1') | list }}"
      tags:
        - always

If you want, you could apply a similar process for "hosts_vars"

::

    - hosts:
        - all
      connection: local
      tasks:
        - name: Include vaulted vars
            include_vars: "{{ item }}"
            with_fileglob: "inventory/hosts_vault_vars/{{ inventory_hostname }}"
      tags:
        - always

In your regulars hosts_vars or group_vars, put ALL your vars !
But if it's a sensitive var to vault, original var should be equal
to a new var.

Example :

::

    group_vars/pp   <= This file is not encrypted, and you can search vars into
    my_database_password: "{{ vault_my_database_password }}"

    vault_vars/pp   <= This file is encrypted but you know it should contain vault_my_database_password
    vault_my_database_password: xxxxxxxxx

Install from smile :
====================

Global install :
----------------

pip install ansible-vault-manager -i https://pypi.org/simple --extra-index-url https://nexus.vitry.intranet/repository/pypi-internal/simple/ --trusted-host nexus.vitry.intranet

Pipenv install :
----------------

Pipfile
::

    [[source]]
    url = "https://pypi.org/simple"
    verify_ssl = true
    name = "pypi"

    [[source]]
    url = "https://nexus.vitry.intranet/repository/pypi-internal/simple/"
    verify_ssl = false
    name = "internal"

    [dev-packages]

    [packages]
    ansible-vault-manager = "*"
