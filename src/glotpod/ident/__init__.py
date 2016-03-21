from pathlib import Path

from glotpod.config import Config
from .__version__ import version as __version__


cfg = Config.from_env('GLOTPOD_IDENT_SETTINGS',
                      str(Path(__file__).with_name('defaults.toml')))


__all__ = ['__version__', 'cfg']
