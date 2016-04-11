glotpod.ident
===============================

|build-status| |license|

Identity micro-service for GlotPod

Installation
------------

You can install glotpod.ident directly from GitHub::

  $ pip install git+https://github.com/te-je/glotpod-ident

That should install all the dependencies for you. If you want to install
directly from source, clone the git repository and run the standard
`python setup.py install` command.

.. note:: If you're on Windows, then you will have trouble installing
          psycopg2. This is because psycopg2 doesn't yet publish a Windows
          wheel for Python 3.5.

          Christoph Gohlke maintains a directory of unofficial binary
          installation packages for Windows, and has `psycopg wheels`_
          compiled against Python 3.5. You can download the appropriate
          one and install it directly with pip (using
          ``pip install --no-index C:\Downloads\psycopg2-2.6.1-cp35-cp35m-win32.whl``
          for example).

.. _psycopg wheels: http://www.lfd.uci.edu/~gohlke/pythonlibs/#psycopg

Dependencies
~~~~~~~~~~~~

* Python 3.5+

Usage
-----

To start an instance of the GlotPod identity microservice::

  $ python -m glotpod.ident

More than one instance can be run. In that case, the requests pertaining to
user identity will be partitioned across the instances.

To run successfully, the instance relies on being able to reach a RabbitMQ
broker as well as a Postgres instance. **The RabbitMQ broker must be the same
instance that is used all of the other GlotPod services** that rely on identity
information (e.g. GlotPod API and GlotPod Auth), however the Postgres
instance may be exclusive to glotpod-ident (but needs to be shared across the
glotpod-ident instances so that they work from the same data).

To specify the locations of these services, set the ``GLOTPOD_IDENT_SETTINGS``
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
``database.postgres.user``           ``glotpod.ident``  A Postgres user which has read/write access to the database
``database.postgres.password``       ---                The password which authenticates the postgres user.
``amqp.ssl``                         ``false``          When true, the API will connect to RabbitMQ server using
                                                        SSL.
``amqp.host``                        ``localhost``      The host for the RabbitMQ broker
``amqp.port``                                           The port for the RabbitMQ broker. If not given, the
                                                        default is chosen based on whether ``ssl = true`` is set,
                                                        so that it matches the defaults for RabbitMQ.
``amqp.login``                       ``guest``
``amqp.password``                    ``guest``
``amqp.login_method``                ``AMQPLAIN``
``amqp.insist``                      ``false``          If true, the server is a bit more adamant at attempting to
                                                        establish a connect with the AMQP broker.
==================================   ================== ==============================================================

Handling Failures
~~~~~~~~~~~~~~~~~

In a peacchy environment, an ident instance will run indefinitely until you
stop it. However, in systems such as these, remote machines may go down and
connections may get lost. In the event of a failure to reach the RabbitMQ
or postgres instances, an ident instance will shut itself down and **exit with
status code 129.**

Because these connection failures are often temporary, the recommended way to
deal with this is to attempt reconnection with an exponential backoff. Since
ident has no such built-in mechanism, you should probably run it inside a
monitor that detects its exit code and restarts it if it needs to.

.. _toml: https://github.com/toml-lang/toml/


.. |build-status| image:: https://travis-ci.org/te-je/glotpod-ident.svg?branch=develop
    :target: https://travis-ci.org/te-je/glotpod-ident
    :alt: build status
    :scale: 100%

.. |license| image:: https://img.shields.io/badge/license-MIT-blue.svg
    :target: https://raw.githubusercontent.com/te-je/glotpod-ident/develop/LICENSE.txt
    :alt: License
    :scale: 100%
