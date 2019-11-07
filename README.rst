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

https://github.com/ansible/ansible/blob/v2.8.6/lib/ansible/parsing/vault/__init__.py#L367

Examples :
==========

Create a new vaulted file :
---------------------------
::

    ansible-vault-manager-client create --vault-path <dir where create new file>

It will ask you for filename, keyring plugin, keyring plugin options,
and encryption password

Create a new vaulted file with generated password :
---------------------------------------------------

::

    pwgen | ansible-vault-manager-client create monfichier   \
        --vault-path vault_vars/  \
        --plugin aws_ssm   \
        --plugin-param region=eu-west-1   \
        --plugin-param profile=customer   \
        --plugin-param path=/ansible/dev/   \
        --stdin-pwd

Automatic integration :
-----------------------

Before run any ansible command (like `ansible-playbook`) you have to
declare your identities list :

::

    # Check usable vault ids and add them to ansible env var
    USABLE_IDS=$(ansible-vault-manager-client get-usable-ids --vault-path "provisioning/inventory/vault_vars/")
    if [ "$USABLE_IDS" != "" ]; then
        export ANSIBLE_VAULT_IDENTITY_LIST="$USABLE_IDS"
    fi

BUGS :
======

* Action create not clean new file or remote vault if an error occurs

Installation :
====================

Global install :
----------------

pip install ansible-vault-manager

Pipenv install :
----------------

pipenv install ansible-vault-manager


TODO :
======

* Implement actions rekey and encrypt
* Make extensible via custom deported plugins added via a "plugin path"
* Make native plugin Hashi Vault
* Make native plugin S3
* Make native plugin MultiPass
* Make native plugin sshfs
* Manage secured cache for credentials fetching

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


Metadata file informations :
============================

A metadata file is used to retrieve all passwords to decrypt vaulted files.
If you loose metadata, you can't know wich passwords where used to encrypt
all vaulted files !!!
When you create your first vaulted file a file named `_metadata.yml` is created
at the root of "vault-path" location.
This name is important and the file follow a structure.

Detailled structure
-------------------

::

    # A list of all "vault-id" used to encrypt files in this directory (see. https://docs.ansible.com/ansible/latest/user_guide/vault.html#multiple-vault-passwords)
    # In normal cases, you should never edit this section manually.
    vault_ids:

        # Plugin used to store password
      - plugin: aws_ssm

        # Config string specific to plugin to fetch password
        id: customer-account:eu-west-1:/ansible/admins/b32b92b8-6ba8-4941-ba48-3b2e73998631:1

        # Could be a list, but probably always one file. Each file should has its own password for security privileges reasons.
        # This parameter is not mandatory, but usefull for debugging, or if you want change a password.
        # Without it, you can't know which file is encrypted with this ID.
        files:
          - prod

      - plugin: aws_ssm
        id: customer-account:eu-west-1:/ansible/dev/4daf2729-7783-43a3-8e3c-9da1b127d8cf:1
        files:
          - webservers

      - plugin: bitwarden
        id: profile:organization:ansible-collection:12f5445a-7783-43a3-8e3c-9da1b127d8cf:1
        files:
          - subdir/all

    # You can MANUALLY add this parameter is some use cases. It permit to include another metadata file (with the same format) and merge all vault_ids.
    # It can be usefull if you share vaulted vars between multiples playbooks scopes
    # This parameter contain a list of absolute or rlative path to current metadata dir
    include:
      - ../../../other_context/inventory/vault_vars/_metadata.yml
      - /mnt/other_secure_place/my_metadata.yml


Plugins doc :
=============

AWS System Manager (SSM parameter store) :
------------------------------------------

AWS SSM permit to store simple secured key/value parameters.
You can apply security policies based on key path, so you can
split admin / devs / other permissions on vault credentials.
All parameters are versionned, AWS keep each versions of parameters.

* profile: Boto profile used (AWS account)
* region:  AWS region code where store parameters
* path:    Path of parameter in SSM, usefull for security policies

Vault ID structure :
`[account profile]:[AWS region]:[parameter path]:[version]`

Bitwarden :
-----------

TODO

Vault ID structure :
`[organization]:[collection]:[name]:[version]`

Multipass Git :
---------------

Multipass is a derived version of https://www.passwordstore.org/ for multi-users.
A set of scripts is available here : https://github.com/toringe/multi-pass

TODO

Vault ID structure :
`[passwords namespace]:[parameter path]:[commit_hash]`

Multi Hashicorp Vault :
-----------------------

You have to install and configure a vault agent, and use Token Helpers (https://www.vaultproject.io/docs/commands/token-helper.html)
to permit access to multiples Hashicorp servers if necessary.

TODO

Vault ID structure :
`[vault instance]:[parameter path]:[version]`

AWS S3 :
--------

TODO
