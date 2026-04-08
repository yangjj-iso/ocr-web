"""Compatibility shim for modules importing `config` from the repository root."""

from app import config as _config
from app.config import *  # noqa: F401,F403

_load_local_env_file = _config._load_local_env_file
_mask_secret = _config._mask_secret
