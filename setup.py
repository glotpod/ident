# -*- coding: utf-8 -*-

from setuptools import setup
from os import path


HERE = path.abspath(path.dirname(__file__))


def read(relpath):
    with open(path.join(HERE, relpath), encoding="utf-8") as f:
        return f.read()

setup(
    name='glotpod.ident',

    description='Identity micro-service for GlotPod',
    long_description="""
{README}

License
-------

{LICENSE}
""".format(README=read("README.rst"), LICENSE=read("LICENSE.rst")),

    author='Te-jé Rodgers',
    author_email='tjd.rodgers@gmail.com',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],

    setup_requires=['setuptools_scm'],
    use_scm_version={"write_to": "src/glotpod/ident/__version__.py"},

    package_dir={'': 'src'},
    namespace_packages=['glotpod'],
    packages=["glotpod.ident"],
    install_requires=['cryptography~=1.3.0', 'SQLAlchemy~=1.0.12',
                      'aiopg~=0.9.2', 'toml~=0.9.1', 'aiohttp~=0.21.6',
                      'voluptuous~=0.8.10', 'jsonpatch~=1.13',
                      'mimetype-match~=1.0.4'],

    extras_require={},

    entry_points={},
)
