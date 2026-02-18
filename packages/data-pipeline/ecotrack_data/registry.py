"""Source registry for auto-discovery and factory creation of data sources."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, TypeVar

from ecotrack.logging import get_logger

from .sources.base import DataSource, DataSourceConfig

logger = get_logger(__name__)

T = TypeVar("T")


class SourceRegistry:
    """Registry that maps source names to :class:`DataSource` classes.

    Supports both manual registration and automatic discovery of
    source implementations from the ``ecotrack_data.sources`` package.

    Example::

        registry = SourceRegistry()
        registry.auto_discover()

        source = registry.create(
            "noaa_climate",
            api_key="<CDO_TOKEN>",
        )
    """

    def __init__(self) -> None:
        self._sources: dict[str, type[DataSource[Any]]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        source_cls: type[DataSource[Any]],
    ) -> None:
        """Register a data source class under a given name.

        Args:
            name: Unique source name (e.g. ``"noaa_climate"``).
            source_cls: The :class:`DataSource` subclass.

        Raises:
            ValueError: If *name* is already registered.
        """
        if name in self._sources:
            raise ValueError(
                f"Source '{name}' is already registered "
                f"({self._sources[name].__name__})"
            )
        self._sources[name] = source_cls
        logger.debug("registry.register", name=name, cls=source_cls.__name__)

    def unregister(self, name: str) -> None:
        """Remove a source from the registry.

        Args:
            name: Source name to remove.

        Raises:
            KeyError: If the name is not registered.
        """
        if name not in self._sources:
            raise KeyError(f"Source '{name}' is not registered")
        del self._sources[name]

    # ------------------------------------------------------------------
    # Auto-discovery
    # ------------------------------------------------------------------

    def auto_discover(self) -> int:
        """Scan ``ecotrack_data.sources`` for :class:`DataSource` subclasses.

        Imports every module in the ``sources`` package and registers
        any concrete :class:`DataSource` subclass found.

        Returns:
            Number of newly discovered sources.
        """
        import ecotrack_data.sources as sources_pkg

        discovered = 0
        package_path = sources_pkg.__path__
        prefix = sources_pkg.__name__ + "."

        for importer, module_name, is_pkg in pkgutil.iter_modules(
            package_path, prefix
        ):
            if is_pkg:
                continue
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                logger.warning(
                    "registry.discover_import_error",
                    module=module_name,
                    error=str(exc),
                )
                continue

            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, DataSource)
                    and obj is not DataSource
                    and not inspect.isabstract(obj)
                ):
                    # Derive a registry name from the class config default
                    name = _infer_source_name(obj, attr_name)
                    if name not in self._sources:
                        self._sources[name] = obj
                        discovered += 1
                        logger.info(
                            "registry.discovered",
                            name=name,
                            cls=obj.__name__,
                            module=module_name,
                        )

        logger.info("registry.auto_discover_complete", total=discovered)
        return discovered

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        *,
        config: DataSourceConfig | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> DataSource[Any]:
        """Create a configured data source instance.

        Args:
            name: Registered source name.
            config: Optional explicit :class:`DataSourceConfig`.
            api_key: Convenience shortcut for API key (forwarded to the
                constructor if it accepts ``api_key``).
            **kwargs: Extra keyword arguments forwarded to the constructor.

        Returns:
            A configured :class:`DataSource` instance.

        Raises:
            KeyError: If *name* is not registered.
        """
        if name not in self._sources:
            raise KeyError(
                f"Source '{name}' not found. "
                f"Available: {sorted(self._sources.keys())}"
            )

        cls = self._sources[name]
        ctor_params = inspect.signature(cls.__init__).parameters

        ctor_kwargs: dict[str, Any] = {}
        if config is not None and "config" in ctor_params:
            ctor_kwargs["config"] = config
        if api_key is not None and "api_key" in ctor_params:
            ctor_kwargs["api_key"] = api_key

        ctor_kwargs.update(kwargs)

        instance = cls(**ctor_kwargs)
        logger.info(
            "registry.create",
            name=name,
            cls=cls.__name__,
        )
        return instance

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def names(self) -> list[str]:
        """Return sorted list of registered source names."""
        return sorted(self._sources.keys())

    def get_class(self, name: str) -> type[DataSource[Any]]:
        """Return the :class:`DataSource` class for *name*.

        Args:
            name: Registered source name.

        Returns:
            The source class.

        Raises:
            KeyError: If *name* is not registered.
        """
        if name not in self._sources:
            raise KeyError(f"Source '{name}' not found")
        return self._sources[name]

    def __contains__(self, name: str) -> bool:
        return name in self._sources

    def __len__(self) -> int:
        return len(self._sources)

    def __repr__(self) -> str:
        return f"SourceRegistry(sources={self.names})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_source_name(cls: type, fallback: str) -> str:
    """Infer a registry name from a DataSource subclass.

    Attempts to instantiate a default config to read ``config.name``.
    Falls back to a snake_case transformation of the class name.

    Args:
        cls: The DataSource subclass.
        fallback: Fallback attribute name from the module.

    Returns:
        A string name suitable for the registry.
    """
    # Try calling the class with no args to read config.name
    try:
        instance = cls.__new__(cls)
        if hasattr(instance, "config") and hasattr(instance.config, "name"):
            return instance.config.name
    except Exception:
        pass

    # Snake-case the class name
    name = fallback
    if name.endswith("Source"):
        name = name[: -len("Source")]

    # Convert CamelCase to snake_case
    result: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------

_default_registry: SourceRegistry | None = None


def get_registry() -> SourceRegistry:
    """Return the default global :class:`SourceRegistry`.

    The registry is lazily initialised and auto-discovers sources on
    first access.

    Returns:
        The singleton :class:`SourceRegistry`.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = SourceRegistry()
        _default_registry.auto_discover()
    return _default_registry


__all__ = ["SourceRegistry", "get_registry"]
