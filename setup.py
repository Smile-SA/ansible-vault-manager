# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

try:
    long_description = open("README.rst").read()
except IOError:
    long_description = ""

setup(
    name="ansible-vault-manager",
    version="0.2.3",
    description="Python tool to manage Ansible vault-ids",
    license="OSL",
    author="Guillaume GILL",
    author_email="guillaume.gill@smile.fr",
    packages=find_packages(),
    install_requires=[
       "future",
       "PyYAML",
    ],
    long_description=long_description,
    entry_points={
        'console_scripts': [
            'ansible-vault-manager-client=ansible_vault_manager.ansible_vault_manager:main',
        ],
    },
    url='https://github.com/Smile-SA/ansible-vault-manager',
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ]
)
