'''
Created on December 30, 2024

@author: Keith Gorlen kgorlen@gmail.com

Classes for units:
    Kilowatts: Power in kilowatts (kW)
    KilowattHours: Energy in kilowatt-hours (kWh)
    DollarsPerKilowatt: Power rate in dollars/kilowatt ($/kW)
    DollarsPerKilowattHour: Energy rate in dollars/kilowatt-hour ($/kWh)
    Dollars: Charges/credits in dollars
'''

__author__ = 'Keith Gorlen'
__all__: list[str] = [
    'Percent',
    'SubscriptionMonths',
    'Kilowatts',
    'KilowattHours',
    'DollarsPerKilowatt',
    'DollarsPerKilowattHour',
    'Dollars',
]

import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext, Context
from functools import total_ordering
from typing import Union, Optional, overload

getcontext().rounding = ROUND_HALF_UP
"""Class Decimal round $0.005 up to $0.01."""


class Percent(Decimal):
    """Percentages."""

    def __new__(cls, value):
        """Create a new Decimal instance with value divided by 100."""
        if isinstance(value, DollarsPerKilowattHour):
            return super().__new__(cls, value.value / 100)

        return super().__new__(cls, Decimal(value) / 100)

    def __repr__(self) -> str:
        return f'Percent({self*100})'

    def __str__(self) -> str:
        """Return string value with % appended."""
        return f'{self*100}%'

    def __format__(self, spec: str, _: Context | None = None) -> str:
        return format(self * 100, spec)

    def quantize(
        self,
        exp: Decimal | int = Decimal('0.001'),
        rounding: str | None = None,
        context: Context | None = None,
    ) -> 'Percent':
        """Return a value equal to the first operand after rounding and having
        the exponent of the second operand.  See decimal.quantize.

        Parameters
        ----------
        exp : Decimal | int, optional
            exponent, by default Decimal('0.001')
        rounding : str | None, optional
            rounding mode, by default None
        context : Context | None, optional
            rounding mode if rounding argument is None, by default None

        Returns
        -------
        Percent
            quantized result
        """
        result = (self * Decimal('100')).quantize(exp, rounding=rounding, context=context)
        return Percent(result)  # type: ignore[return-value]


class SubscriptionMonths(Decimal):
    """Length of subscription period in fractional months."""

    def __repr__(self) -> str:
        return f'SubscriptionMonths({self})'

    def quantize(self) -> 'SubscriptionMonths':  # type: ignore[override]
        """Return a value equal to the first operand after rounding and having
        the exponent of the second operand.  See decimal.quantize."""
        return super().quantize(Decimal('0.001'))  # type: ignore[return-value]


@total_ordering
class Kilowatts:
    """Power in kilowatts (kW)."""

    def __init__(self, value: Union[str, int, float, Decimal, 'Kilowatts']) -> None:

        """Initialize a Kilowatts instance.

        Parameters
        ----------
        value : Union[str, int, float, Decimal, Kilowatts]
            Kilowatts

        Raises
        ------
        TypeError
            Kilowatts can only be initialized with a str, int, float, or Kilowatts
        """
        self.value: float

        if isinstance(value, float):
            self.value = value
            return

        if isinstance(value, Kilowatts):
            self.value = value.value
            return

        if isinstance(value, str):
            self.value = float(value.replace(',', ''))
        elif isinstance(value, (int, Decimal)):
            self.value = float(value)
        else:
            raise TypeError(
                'Kilowatts can only be initialized with a str, int, float, or Kilowatts'
            )

    def __repr__(self) -> str:
        return f'Kilowatts({self.value})'

    def __str__(self) -> str:
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)

    def __float__(self) -> float:
        return float(self.value)

    def __eq__(
        self, other: Union[str, int, float, Decimal, 'Kilowatts']  # type: ignore[override]
    ) -> bool:
        return self.value == Kilowatts(other).value

    def __lt__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> bool:
        return self.value < Kilowatts(other).value

    def __neg__(self) -> 'Kilowatts':
        return Kilowatts(-self.value)

    def __add__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> 'Kilowatts':
        return Kilowatts(self.value + Kilowatts(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> 'Kilowatts':
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> 'Kilowatts':
        self.value += Kilowatts(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> 'Kilowatts':
        return Kilowatts(self.value - Kilowatts(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> 'Kilowatts':
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, 'Kilowatts']) -> 'Kilowatts':
        self.value -= Kilowatts(other).value
        return self

    def __mul__(self, other: Union[int, float, Decimal, Percent]) -> 'Kilowatts':
        if isinstance(other, (int, float)):
            return Kilowatts(self.value * other)

        if isinstance(other, (Decimal, Percent)):
            return Kilowatts(Decimal(self.value) * other)

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal, Percent]) -> 'Kilowatts':
        self.value = self.__mul__(other).value
        return self

    @overload
    def __truediv__(self, other: 'Kilowatts') -> float: ...

    @overload
    def __truediv__(self, other: Union[int, float, Decimal]) -> 'Kilowatts': ...

    def __truediv__(
        self, other: Union[int, float, Decimal, 'Kilowatts']
    ) -> Union[float, 'Kilowatts']:
        """True division (/) operator.

        Returns
        -------
        Kilowatts
            Divide by int, float, or Decimal.
        float
            Divide by Kilowatts
        """
        if isinstance(other, (int, float)):
            return Kilowatts(self.value / other)

        if isinstance(other, Decimal):
            return Kilowatts(self.value / float(other))

        if isinstance(other, Kilowatts):
            return self.value / other.value

        return NotImplemented


@total_ordering
class KilowattHours:
    """Energy in kilowatt-hours (kWh)."""

    def __init__(self, value: Union[str, int, float, Decimal, 'KilowattHours']) -> None:
        """Initialize a KilowattHours instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  'KilowattHours'
            Commas are removed from str.

        Raises
        ------
        TypeError
            KilowattHours can only be initialized with a str, int, float, Decimal, or None
        """
        self.value: Decimal

        if isinstance(value, KilowattHours):
            self.value = value.value
            return

        if isinstance(value, str):
            self.value = Decimal(value.replace(',', ''))
        elif isinstance(value, (int, float, Decimal)):
            self.value = Decimal(value)
        else:
            raise TypeError(
                'KilowattHours can only be initialized with a str, int, float, Decimal, or None'
            )

        self.value = self.value.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

    def __repr__(self) -> str:
        return f'KilowattHours({self.value})'

    def __str__(self) -> str:
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)

    def __float__(self) -> float:
        return float(self.value)

    def __eq__(
        self, other: Union[str, int, float, Decimal, 'KilowattHours']  # type: ignore[override]
    ) -> bool:
        return self.value == KilowattHours(other).value

    def __lt__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> bool:
        return self.value < KilowattHours(other).value

    def __neg__(self) -> 'KilowattHours':
        return KilowattHours(-self.value)

    def __add__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> 'KilowattHours':
        return KilowattHours(self.value + KilowattHours(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> 'KilowattHours':
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> 'KilowattHours':
        self.value += KilowattHours(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> 'KilowattHours':
        return KilowattHours(self.value - KilowattHours(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> 'KilowattHours':
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, 'KilowattHours']) -> 'KilowattHours':
        self.value -= KilowattHours(other).value
        return self

    @overload
    def __mul__(self, other: Union[int, float, Decimal]) -> 'KilowattHours': ...

    @overload
    def __mul__(self, other: 'DollarsPerKilowattHour') -> 'Dollars': ...

    def __mul__(
        self, other: Union[int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> Union['Dollars', 'KilowattHours']:
        if isinstance(other, (int, Decimal)):
            return KilowattHours(self.value * other)

        if isinstance(other, float):
            return KilowattHours(self.value * Decimal(other))

        if isinstance(other, DollarsPerKilowattHour):
            return Dollars(Decimal(self.value) * other.value)

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal]) -> 'KilowattHours':  # type: ignore[misc]
        self.value = self.__mul__(other).value
        return self

    @overload
    def __truediv__(self, other: 'KilowattHours') -> Decimal: ...

    @overload
    def __truediv__(self, other: Union[int, float, Decimal]) -> 'KilowattHours': ...

    def __truediv__(
        self, other: Union[int, float, Decimal, 'KilowattHours']
    ) -> Union[Decimal, 'KilowattHours']:
        if isinstance(other, (int, float)):
            return KilowattHours(self.value / Decimal(other))

        if isinstance(other, Decimal):
            return KilowattHours(self.value / other)

        if isinstance(other, KilowattHours):
            return self.value / other.value

        return NotImplemented


@total_ordering
class DollarsPerKilowatt:
    """Subscription (a.k.a demand) rate in dollars/kilowatt ($/kW)."""

    def __init__(self, value: Union[str, int, float, Decimal, 'DollarsPerKilowatt']) -> None:
        """Initialize a DollarsPerKilowatt instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  'DollarsPerKilowatt'
            Commas are removed from str.

        Raises
        ------
        TypeError
            DollarsPerKilowatt can only be initialized with a str, int, float, Decimal,
            or DollarsPerKilowatt
        """
        self.value: Decimal

        if isinstance(value, DollarsPerKilowatt):
            self.value = value.value
            return

        if isinstance(value, (str, int, float, Decimal)):
            self.value = Decimal(value)
        else:
            raise TypeError(
                'DollarsPerKilowatt can only be initialized with a str, int, float, Decimal, '
                'or DollarsPerKilowatt'
            )

        self.value = self.value.quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)

    def __repr__(self) -> str:
        return f'DollarsPerKilowatt({self.value})'

    def __str__(self) -> str:
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)

    def __float__(self) -> float:
        return float(self.value)

    def __eq__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']  # type: ignore[override]
    ) -> bool:
        return self.value == DollarsPerKilowatt(other).value

    def __lt__(self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']) -> bool:
        return self.value < DollarsPerKilowatt(other).value

    def __neg__(self) -> 'DollarsPerKilowatt':
        return DollarsPerKilowatt(-self.value)

    def __add__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']
    ) -> 'DollarsPerKilowatt':
        return DollarsPerKilowatt(self.value + DollarsPerKilowatt(other).value)

    def __radd__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']
    ) -> 'DollarsPerKilowatt':
        return self.__add__(other)

    def __iadd__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']
    ) -> 'DollarsPerKilowatt':
        self.value += DollarsPerKilowatt(other).value
        return self

    def __sub__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']
    ) -> 'DollarsPerKilowatt':
        return DollarsPerKilowatt(self.value - DollarsPerKilowatt(other).value)

    def __rsub__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']
    ) -> 'DollarsPerKilowatt':
        return self.__sub__(other)

    def __isub__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowatt']
    ) -> 'DollarsPerKilowatt':
        self.value -= DollarsPerKilowatt(other).value
        return self

    @overload
    def __mul__(self, other: Union[int, float, Decimal]) -> 'DollarsPerKilowatt': ...

    @overload
    def __mul__(self, other: Kilowatts) -> 'Dollars': ...

    def __mul__(
        self, other: Union[int, float, Decimal, Kilowatts]
    ) -> Union['Dollars', 'DollarsPerKilowatt']:
        if isinstance(other, (int, Decimal)):
            return DollarsPerKilowatt(self.value * other)

        if isinstance(other, float):
            return DollarsPerKilowatt(float(self.value) * other)

        if isinstance(other, Kilowatts):
            return Dollars(self.value * Decimal(other.value))

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal]) -> 'DollarsPerKilowatt':  # type: ignore[misc]
        self.value = self.__mul__(other).value
        return self

    def __truediv__(self, other: Union[int, float, Decimal]) -> 'Kilowatts':
        if isinstance(other, (int, float)):
            return Kilowatts(self.value / Decimal(other))

        if isinstance(other, Decimal):
            return Kilowatts(self.value / other)

        return NotImplemented


@total_ordering
class DollarsPerKilowattHour:
    """Energy rate in dollars/kilowatt-hour ($/kWh)."""

    def __init__(self, value: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']) -> None:
        """Initialize a DollarsPerKilowattHour instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  'DollarsPerKilowattHour'
            '($d.ddddd)' indicates a negative rate.
            Commas are removed from str.

        Raises
        ------
        TypeError
            DollarsPerKilowattHour can only be initialized with a str, int, float, Decimal,
            or DollarsPerKilowattHour
        """
        self.value: Decimal

        if isinstance(value, DollarsPerKilowattHour):
            self.value = value.value
            return

        if isinstance(value, str):
            if value[0] == '(' and value[-1] == ')':
                self.value = -Decimal(value[1:-1])
            else:
                self.value = Decimal(value)
        elif isinstance(value, (int, float, Decimal)):
            self.value = Decimal(value)
        else:
            raise TypeError(
                'DollarsPerKilowattHour can only be initialized with a str, int, float, Decimal, '
                'or DollarsPerKilowattHour'
            )

        self.value = self.value.quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)

    def __repr__(self) -> str:
        return f'DollarsPerKilowattHour({self.value})'

    def __str__(self) -> str:
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)

    def __float__(self) -> float:
        return float(self.value)

    def __eq__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']  # type: ignore[override]
    ) -> bool:
        return self.value == DollarsPerKilowattHour(other).value

    def __lt__(self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']) -> bool:
        return self.value < DollarsPerKilowattHour(other).value

    def __neg__(self) -> 'DollarsPerKilowattHour':
        return DollarsPerKilowattHour(-self.value)

    def __add__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> 'DollarsPerKilowattHour':
        return DollarsPerKilowattHour(self.value + DollarsPerKilowattHour(other).value)

    def __radd__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> 'DollarsPerKilowattHour':
        return self.__add__(other)

    def __iadd__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> 'DollarsPerKilowattHour':
        self.value += DollarsPerKilowattHour(other).value
        return self

    def __sub__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> 'DollarsPerKilowattHour':
        return DollarsPerKilowattHour(self.value - DollarsPerKilowattHour(other).value)

    def __rsub__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> 'DollarsPerKilowattHour':
        return self.__sub__(other)

    def __isub__(
        self, other: Union[str, int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> 'DollarsPerKilowattHour':
        self.value -= DollarsPerKilowattHour(other).value
        return self

    @overload
    def __mul__(self, other: Union[int, float, Decimal]) -> 'DollarsPerKilowattHour': ...

    @overload
    def __mul__(self, other: KilowattHours) -> 'Dollars': ...

    def __mul__(
        self, other: Union[int, float, Decimal, KilowattHours]
    ) -> Union['Dollars', 'DollarsPerKilowattHour']:
        if isinstance(other, (int, Decimal)):
            return DollarsPerKilowattHour(self.value * other)

        if isinstance(other, float):
            return DollarsPerKilowattHour(float(self.value) * other)

        if isinstance(other, KilowattHours):
            return Dollars(self.value * other.value)

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal]) -> 'DollarsPerKilowattHour':  # type: ignore[misc]
        self.value = self.__mul__(other).value
        return self

    def __truediv__(self, other: Union[int, float, Decimal]) -> 'DollarsPerKilowattHour':
        if isinstance(other, (int, float)):
            return DollarsPerKilowattHour(self.value / Decimal(other))

        if isinstance(other, Decimal):
            return DollarsPerKilowattHour(self.value / other)

        return NotImplemented


@total_ordering
class Dollars:
    """Charges/credits in dollars."""

    def __init__(self, value: Union[str, int, float, Decimal, 'Dollars']) -> None:
        """Initialize a Dollars instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  'Dollars'
            Commas are removed from str.

        Raises
        ------
        TypeError
            Dollars can only be initialized with a str, int, float, or Decimal
        """
        self.value: Decimal

        if isinstance(value, Dollars):
            self.value = value.value
            return

        if isinstance(value, str):
            self.value = Decimal(value.replace(',', ''))
        elif isinstance(value, (int, float, Decimal)):
            self.value = Decimal(value)
        else:
            raise TypeError('Dollars can only be initialized with a str, int, float, or Decimal')

        self.value = self.value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def __repr__(self) -> str:
        return f'Dollars({self.value})'

    def __str__(self) -> str:
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)

    def __float__(self) -> float:
        return float(self.value)

    def __eq__(
        self, other: Union[str, int, float, Decimal, 'Dollars']  # type: ignore[override]
    ) -> bool:
        return self.value == Dollars(other).value

    def __lt__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> bool:
        return self.value < Dollars(other).value

    def __neg__(self) -> 'Dollars':
        return Dollars(-self.value)

    def __abs__(self) -> 'Dollars':
        return Dollars(self.value if self.value >= 0 else -self.value)

    def __add__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> 'Dollars':
        return Dollars(self.value + Dollars(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> 'Dollars':
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> 'Dollars':
        self.value += Dollars(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> 'Dollars':
        return Dollars(self.value - Dollars(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> 'Dollars':
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, 'Dollars']) -> 'Dollars':
        self.value -= Dollars(other).value
        return self

    def __mul__(self, other: Union[int, float, Decimal, Percent]) -> 'Dollars':
        if isinstance(other, (int, Decimal, Percent)):
            return Dollars(self.value * other)

        if isinstance(other, float):
            return Dollars(float(self.value) * other)

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal, Percent]) -> 'Dollars':
        self.value = self.__mul__(other).value
        return self

    @overload
    def __truediv__(self, other: 'Dollars') -> Decimal: ...

    @overload
    def __truediv__(self, other: Union[int, float]) -> 'Dollars': ...

    @overload
    def __truediv__(self, other: Kilowatts) -> DollarsPerKilowatt: ...

    @overload
    def __truediv__(self, other: KilowattHours) -> DollarsPerKilowattHour: ...

    def __truediv__(
        self, other: Union[int, float, Kilowatts, KilowattHours, 'Dollars']
    ) -> Union[Decimal, DollarsPerKilowatt, DollarsPerKilowattHour, 'Dollars']:
        """True division (/) operator.

        Returns
        -------
        Decimal
            Divide by Dollars
        Dollars
            Divide by int or float.
        DollarsPerKilowatt
            Divide by Kilowatts.
        DollarsPerKilowattHour
            Divide by KilowattHours.
        Decimal
            Divide by Dollars

        Raises
        ------
        TypeError
            Invalid parameter type.
        """
        if isinstance(other, int):
            return Dollars(self.value / other)

        if isinstance(other, float):
            return Dollars(float(self.value) / other)

        if isinstance(other, Dollars):
            return Decimal(self.value / other.value)

        if isinstance(other, Kilowatts):
            return DollarsPerKilowatt(self.value / Decimal(other.value))

        if isinstance(other, KilowattHours):
            return DollarsPerKilowattHour(self.value / other.value)

        return NotImplemented


if __name__ == '__main__':

    def test(Class: type, val: type, convert: Optional[type] = None, comma=True):
        """Test numeric class

        Parameters
        ----------
        Class : type
            Class to be tested.
        val : type
            Numeric type of class: float or Decimal.
        comma : bool, optional
            Test __init__ with number string containing comma thousands separator, by default True.
        """
        s = '1,234.56' if comma else '1_234.56'
        assert type(Class(s)) == Class, f'{Class.__name__}'  # pylint: disable=unidiomatic-typecheck
        assert Class(s).value == Class(1_234.56), f'{Class.__name__}'
        assert Class(1234).value == val(1234), f'{Class.__name__}'
        assert Class(0.50).value == val('.50'), f'{Class.__name__}'
        assert Class(Class(0)).value == 0, f'{Class.__name__}'
        assert Class(0) == 0, f'{Class.__name__}'
        assert Class(0) < 1, f'{Class.__name__}'
        assert Class(1) <= 1, f'{Class.__name__}'
        assert Class(1) > 0, f'{Class.__name__}'
        assert Class(1) >= 1, f'{Class.__name__}'
        assert -Class(1) == -1, f'{Class.__name__}'
        assert Class(1) + 1 == 2, f'{Class.__name__}'
        assert 1 + Class(1) == 2, f'{Class.__name__}'
        obj = Class(1)
        orig = obj
        obj += 1
        assert obj == 2, f'{Class.__name__}'
        assert id(obj) == id(orig), f'{Class.__name__}'
        assert Class(1) - 1 == 0, f'{Class.__name__}'
        assert 1 - Class(1) == 0, f'{Class.__name__}'
        obj = Class(1)
        orig = obj
        obj -= 1
        assert obj == 0, f'{Class.__name__}'
        assert id(obj) == id(orig), f'{Class.__name__}'
        assert Class(2) * 2 == 4, f'{Class.__name__}'
        assert 2 * Class(2) == 4, f'{Class.__name__}'
        obj = Class(2)
        orig = obj
        obj *= 2
        assert obj == 4, f'{Class.__name__}'
        assert id(obj) == id(orig), f'{Class.__name__}'
        assert Class(4) / 2 == 2, f'{Class.__name__}'
        assert float(Class(0.50)) == 0.5, f'{Class.__name__}'
        if convert:
            assert (
                (result := Class(2.2) * convert(2))
                and result == Dollars(4.4)
                and isinstance(result, Dollars)
            ), f'{Class.__name__}'

    print(getcontext())
    assert type(Percent(12.3456)) == Percent, 'Percent'  # pylint: disable=unidiomatic-typecheck
    assert (
        type(Percent(12.3456).quantize()) == Percent  # pylint: disable=unidiomatic-typecheck
    ), 'Percent'
    assert Percent(12.3456).quantize() == Decimal('.12346'), 'Percent'
    assert repr(Percent('12.34')) == f'{Percent.__name__}(12.3400)', 'Percent'
    assert str(Percent('12.34')) == '12.3400%'
    assert f'{Percent(12.34):.3f}' == '12.340'

    assert SubscriptionMonths(1.1234).quantize() == SubscriptionMonths(
        '1.123'
    ), 'SubscriptionMonths'
    assert (
        repr(SubscriptionMonths('1.1234')) == f'{SubscriptionMonths.__name__}(1.1234)'
    ), 'SubscriptionMonths'

    test(Dollars, Decimal)
    assert Dollars(1) * Percent(50) == Dollars(0.50), 'Dollars'
    assert Dollars(1) / Kilowatts(2) == DollarsPerKilowatt(0.5), 'Dollars'
    assert Dollars(1) / KilowattHours(2) == DollarsPerKilowattHour(0.5), 'Dollars'
    assert Dollars(1) / Dollars(2) == Decimal('0.5'), 'Dollars'
    assert repr(Dollars('1,234.56')) == f'{Dollars.__name__}(1234.56)', 'Dollars'
    assert str(Dollars('1,234.56')) == '1234.56', 'Dollars'
    assert f'{Dollars("1234.56"):8,.02f}' == '1,234.56', 'Dollars'

    test(Kilowatts, float, convert=DollarsPerKilowatt, comma=False)
    assert Kilowatts(1) * Percent(50) == Kilowatts(0.50)
    assert Kilowatts(1) / Kilowatts(2) == Decimal('0.5'), 'Kilowatts'
    assert repr(Kilowatts('1,234.56')) == f'{Kilowatts.__name__}(1234.56)', 'Kilowatts'
    assert str(Kilowatts('1,234.56')) == '1234.56', 'Kilowatts'
    assert f'{Kilowatts("12.345"):5.3g}' == ' 12.3', 'Kilowatts'

    test(KilowattHours, Decimal, convert=DollarsPerKilowattHour)
    assert KilowattHours(1) / KilowattHours(2) == Decimal('0.5'), 'KilowattHours'
    assert (
        repr(KilowattHours('1,234.123456')) == f'{KilowattHours.__name__}(1234.123456)'
    ), 'KilowattHours'
    assert str(KilowattHours('1,234.123456')) == '1234.123456', 'KilowattHours'
    assert f'{KilowattHours("1,234.123456"):12,.6f}' == '1,234.123456', 'KilowattHours'

    test(DollarsPerKilowatt, Decimal, convert=Kilowatts, comma=False)
    assert (
        repr(DollarsPerKilowatt('1.12345')) == f'{DollarsPerKilowatt.__name__}(1.12345)'
    ), 'DollarsPerKilowatt'
    assert str(DollarsPerKilowatt('1.12345')) == '1.12345', 'DollarsPerKilowatt'
    assert f'{DollarsPerKilowatt("1.12345"):.5f}' == '1.12345', 'DollarsPerKilowatt'
    test(DollarsPerKilowattHour, Decimal, convert=KilowattHours, comma=False)
    assert str(DollarsPerKilowattHour('(1.12345)')) == '-1.12345', 'DollarsPerKilowattHour'
    assert (
        repr(DollarsPerKilowattHour('1.12345')) == f'{DollarsPerKilowattHour.__name__}(1.12345)'
    ), 'DollarsPerKilowattHour'
    assert str(DollarsPerKilowattHour('1.12345')) == '1.12345', 'DollarsPerKilowattHour'
    assert f'{DollarsPerKilowattHour("1.12345"):.5f}' == '1.12345', 'DollarsPerKilowattHour'
    assert f'{DollarsPerKilowattHour("(1.12345)"):.5f}' == '-1.12345', 'DollarsPerKilowattHour'

    print('PASS')
    sys.exit(0)
