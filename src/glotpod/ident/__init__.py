import toml

from os import environ
from pathlib import Path

from glotpod.ident.__version__ import version as __version__


def load_config():
    defaults = {
        'database': {
            'encryption-key': None,
         },
        'services': {
            'github': {'client_id': None, 'client_secret': None},
        },
    }

    if 'GLOTPOD_IDENT_SETTINGS' in environ:
        with open(environ['GLOTPOD_IDENT_SETTINGS']) as fh:
            text = fh.read()
            defaults.update(toml.loads(text))

    return defaults


cfg = load_config()



__all__ = ['__version__', 'cfg']
