"""Base data processor abstractions."""
from __future__ import annotations

import abc
from typing import Any, Generic, TypeVar

T_in = TypeVar("T_in")
T_out = TypeVar("T_out")


class DataProcessor(abc.ABC, Generic[T_in, T_out]):
    """Abstract data processor for ETL pipeline stages.

    Defines the contract for a processing step that takes input of
    type *T_in*, validates it, transforms it into *T_out*, and
    validates the output.

    Concrete implementations should be stateless where possible so
    that multiple instances can be run concurrently.
    """

    @abc.abstractmethod
    async def process(self, data: T_in) -> T_out:
        """Process input data and return transformed output.

        Args:
            data: Input data of type *T_in*.

        Returns:
            Transformed data of type *T_out*.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def validate_input(self, data: T_in) -> bool:
        """Validate input data before processing.

        Args:
            data: Input data to validate.

        Returns:
            ``True`` if the data is valid for processing.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def validate_output(self, data: T_out) -> bool:
        """Validate output data after processing.

        Args:
            data: Output data to validate.

        Returns:
            ``True`` if the processed data meets quality requirements.
        """
        ...  # pragma: no cover

    async def safe_process(self, data: T_in) -> T_out:
        """Process data with input/output validation guards.

        Validates the input before processing, then validates the
        output after.  Raises :class:`ValueError` if either check fails.

        Args:
            data: Input data.

        Returns:
            Validated output data.

        Raises:
            ValueError: If input or output validation fails.
        """
        if not await self.validate_input(data):
            raise ValueError(f"{self.__class__.__name__}: input validation failed")
        result = await self.process(data)
        if not await self.validate_output(result):
            raise ValueError(f"{self.__class__.__name__}: output validation failed")
        return result


__all__ = ["DataProcessor"]
