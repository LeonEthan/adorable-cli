__all__ = ["__version__"]

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("adorable-cli")
except Exception:
    # Fallback when running from source or when distribution package is not installed
    __version__ = "0.2.13"