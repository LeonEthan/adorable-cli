__all__ = ["__version__"]

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("adorable-cli")
except Exception:
    # 源码运行或未安装分发包时的回退
    __version__ = "0.0.0"