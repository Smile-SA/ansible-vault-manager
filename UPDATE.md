`vim ~/.pypirc`
```
[distutils]
index-servers =
    internal

[internal]
repository: https://nexus.vitry.intranet/repository/pypi-internal/
ca_cert: /etc/ssl/certs/ca-certificates.crt
```


```
pip install twine
```

```
python setup.py sdist
twine upload -r internal dist/ansible-vault-manager*.tar.gz
```
