"""API modules: one router per module, selected by deployment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable

from fastapi import APIRouter


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ApiModule:
    name: str
    router: APIRouter


class ModuleRegistry:
    def __init__(self, modules: Iterable[ApiModule]):
        registered: dict[str, ApiModule] = {}
        for module in modules:
            if module.name in registered:
                raise ConfigurationError(f'Duplicate API module: {module.name}')
            registered[module.name] = module
        self._modules = MappingProxyType(registered)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._modules)

    def select(self, names: Iterable[str] | None) -> tuple[ApiModule, ...]:
        """The named modules in registration order; ``None`` selects every module."""
        if names is None:
            return tuple(self._modules.values())
        names = set(names)
        unknown = names - set(self._modules)
        if unknown:
            raise ConfigurationError('Unknown API modules: ' + ', '.join(sorted(unknown)))
        return tuple(module for name, module in self._modules.items() if name in names)
