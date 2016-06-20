Identity Micro-Service
======================

Identity micro-service for the Geniphi Common Platform.

Dependencies
~~~~~~~~~~~~

* Python 3.5+


Installation
------------

Run pip install to install directly from ssh::

  $ git+ssh://alpha.geniglotpod.com/var/apps/common/ident.git

Usage
-----

To start an instance of the Identity micro-service::

  $ python -m aiohttp.web -H localhost -P 5000 glotpod.ident:init_app

More than one instance can be run. In that case, the requests pertaining to
user identity will be partitioned across the instances.

To run successfully, the instance relies on being able to reach a Postgres
instance. The Postgres instance may be exclusive to the Identity service, or
may be shared with other micro-services *as long as* the configured database
remains exclusive to Identity.

To specify the locations of these services, set the ``PHI_IDENT_SETTINGS``
environment variable to a TOML configuration file with these values:

==================================   ================== ==============================================================
Key                                  Default            Description
==================================   ================== ==============================================================
``database.encryption_key``          ---                A Fernet encryption key for sensitive values in the database.
                                                        It's used to encrypt access tokens for external services.
                                                        This needs to be base32 encoded.
``database.postgres.host``           ``localhost``      Which host is Postgres listening on?
``database.postgres.port``           ``5432``           Which port is Postgres listening on?
``database.postgres.database``       ``glotpod.ident``      A (pre-created) database in Postgres which glotpod-ident will
                                                        use for its tables.
``database.postgres.user``           ``glotpod.ident``      A Postgres user which has read/write access to the database
``database.postgres.password``       ---                The password which authenticates the postgres user.
==================================   ================== ==============================================================

Handling Failures
~~~~~~~~~~~~~~~~~

In a peacchy environment, an ident instance will run indefinitely until you
stop it. However, in systems such as these, remote machines may go down and
connections may get lost. In the event of a failure to reach the postgres
instance, an ident instance may shut itself down and **exit with
status code 129.**

Because these connection failures are often temporary, the recommended way to
deal with this is to attempt reconnection with an exponential backoff. Since
ident has no such built-in mechanism, you should probably run it inside a
monitor that detects its exit code and restarts it if it needs to.

.. _toml: https://github.com/toml-lang/toml/
