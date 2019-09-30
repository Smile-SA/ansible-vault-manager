This tool is a manager to make easier and sharable ansible-vault integration.
It's almost a prerequisite to combine ansible-vault and CI/CD.
With it you don't need anymore to share vault passphrase with other people.
You can rotate them transparently for security good practices.
You can use "keyring plugins" to extend it and store passphrases on AWS SSM, Bitwarden, or other secured storage system.

Create a new vaulted file :

`ansible-vault-manager-client --action create --vault-path <dir where create new file>`

It will ask you for filename, keyring plugin, keyring plugin options, and encryption password

Automatic integration :

Before run any ansible command (like `ansible-playbook`) you have to declare your identities list :

```bash
# Check usable vault ids and add them to ansible env var
USABLE_IDS=$(ansible-vault-manager-client --action get-usable-ids --vault-path "provisioning/inventory/vault_vars/")
echo $USABLE_IDS
if [ "$USABLE_IDS" != "" ]; then
    export ANSIBLE_VAULT_IDENTITY_LIST="$USABLE_IDS"
fi
```

TODO :

* Make extensible via custom deported plugins added via a "plugin path"
* Make native plugin Hashi Vault
* Make native plugin S3
* Make native plugin sshfs
