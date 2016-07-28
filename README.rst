Identity Micro-Service
======================

|circle|


Identity micro-service for the GlotPod.

Dependencies
~~~~~~~~~~~~

* Python 3.5+


Installation
------------

Run pip install to install directly from ssh::

  $ git+https://github.com/glotpod/ident.git

Usage
-----

To start an instance of the Identity micro-service::

  $ python -m aiohttp.web -H localhost -P 5000 glotpod.ident:init_app

To run successfully, the instance relies on being able to reach a Postgres
instance. The Postgres instance may be exclusive to the Identity service, or
may be shared with other micro-services *as long as* the configured database
remains exclusive to Identity.

To specify the locations of these services, set the ``IDENT_SETTINGS``
environment variable to a TOML configuration file with these values:

==================================   ================== ==============================================================
Key                                  Default            Description
==================================   ================== ==============================================================
``database.encryption_key``          ---                A Fernet encryption key for sensitive values in the database.
                                                        It's used to encrypt access tokens for external services.
                                                        This needs to be base32 encoded.
``database.postgres.host``           ``localhost``      Which host is Postgres listening on?
``database.postgres.port``           ``5432``           Which port is Postgres listening on?
``database.postgres.database``       ``glotpod.ident``  A (pre-created) database in Postgres which glotpod-ident will
                                                        use for its tables.
``database.postgres.user``           ``postgres``       A Postgres user which has read/write access to the database
``database.postgres.password``       ---                The password which authenticates the postgres user.
==================================   ================== ==============================================================

.. _toml: https://github.com/toml-lang/toml/
.. |circle| image:: https://circleci.com/gh/glotpod/ident.svg?style=svg
    :target: https://circleci.com/gh/glotpod/ident
