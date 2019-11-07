`vim ~/.pypirc`
```
[distutils]
index-servers =
   internal
   test
   prod

[internal]
repository: https://nexus.vitry.intranet/repository/pypi-internal/
ca_cert: /etc/ssl/certs/ca-certificates.crt

[test]
repository: https://test.pypi.org/legacy/

[prod]
repository: https://upload.pypi.org/legacy/
```


```
pip install twine webencodings
```

```
python setup.py sdist
twine upload -r internal dist/*
twine upload -r test dist/*
twine upload -r prod dist/*
```
