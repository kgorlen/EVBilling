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
    'RE_DATE',
    'RE_PERIOD',
    'RE_DOLLARS',
    'RE_kWh',
    'RE_RATES',
    'SUBMETER_PLACES_kW',
    'SUBMETER_PLACES_kWh',
    'Percent',
    'SubscriptionMonths',
    'Kilowatts',
    'KilowattHours',
    'DollarsPerKilowatt',
    'DollarsPerKilowattHour',
    'Dollars',
]

from decimal import Decimal, ROUND_HALF_UP, getcontext, Context
from functools import total_ordering
from typing import Union, overload, Self

getcontext().rounding = ROUND_HALF_UP
"""Class Decimal round $0.005 up to $0.01."""

#
# Global constants
#

RE_DATE = r'((?:0?[1-9]|1[012])/(?:0?[1-9]|[12]\d|3[01])/(?:19\d\d|20\d\d))'
"""Regular expression for mm/dd/yyyy dates."""
RE_PERIOD = rf'(?m)^{RE_DATE}(?: (?:\W |to )?{RE_DATE})?'
"""Regular expression for mm/dd/yyy - mm/dd/yyy date range."""
RE_DOLLARS = r'\$?(-?\d{1,3}(?:,?\d{3})*\.\d{2})'
"""Regular expression for nnn,nnn.nn dollars, optional $ sign."""
RE_kWh = r'(\d{1,3}(?:,?\d{3})*\.\d{6})'
"""Regular expression for for nnn,nnn.nnnnnn kWh."""
RE_RATES = r'\$(\d{1,3}\.\d{5})'
"""Regular expression for $nnn.nnnnn dollars/kWh."""

SUBMETER_PLACES_kW = 3
"""Number of decimal places for submeter kW values."""
SUBMETER_PLACES_kWh = 3
"""Number of decimal places for submeter kWh values."""

class Percent(Decimal):
    """Percentages."""

    def __new__(cls, value):
        """Create a new Decimal instance with value divided by 100."""
        if isinstance(value, DollarsPerKilowattHour):
            return super().__new__(cls, value.value / 100)

        return super().__new__(cls, Decimal(value) / 100)

    def __repr__(self) -> str:
        s = str(self)[:-1]  # Remove trailing '%'
        return 'Percent(' + s + ')'

    def __str__(self) -> str:
        """Return string value with % appended."""
        return f'{self:%}'

    def __format__(self, spec: str, _: Context | None = None) -> str:
        if spec and spec[-1] == '%':
            return super().__format__(spec)

        return Decimal(self * 100).__format__(spec)

    def quantize(
        self,
        exp: Decimal | int = Decimal('0.001'),
        rounding: str | None = None,
        context: Context | None = None,
    ) -> Self:
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
        result = Decimal(self * 100).quantize(exp, rounding=rounding, context=context)
        return Percent(result)  # type: ignore[return-value]


class SubscriptionMonths(Decimal):
    """Length of subscription period in fractional months."""

    def __repr__(self) -> str:
        return f'SubscriptionMonths({str(self)})'


@total_ordering
class Kilowatts:
    """Power in kilowatts (kW)."""

    def __init__(self, value: Union[str, int, float, Decimal, Self]) -> None:
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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, int, float, Decimal, type(self))):
            return self.value == Kilowatts(other).value
        return NotImplemented

    def __lt__(self, other: Union[str, int, float, Decimal, Self]) -> bool:
        return self.value < Kilowatts(other).value

    def __neg__(self) -> Self:
        return type(self)(-self.value)

    def __abs__(self):
        return type(self)(self.value if self.value >= 0 else -self.value)

    def __round__(self, ndigits: int = 0):
        return type(self)(round(self.value, ndigits))

    def __add__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value + Kilowatts(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value += Kilowatts(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value - Kilowatts(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value -= Kilowatts(other).value
        return self

    def __mul__(self, other: Union[int, float, Decimal, Percent]) -> Self:
        if isinstance(other, (int, float, Decimal, Percent)):
            return type(self)(self.value * float(other))

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal, Percent]) -> Self:
        self.value = self.__mul__(other).value
        return self

    @overload
    def __truediv__(self, other: Self) -> float: ...

    @overload
    def __truediv__(self, other: Union[int, float, Decimal]) -> Self: ...

    def __truediv__(self, other: Union[int, float, Decimal, Self]) -> Union[float, Self]:
        """True division (/) operator.

        Returns
        -------
        Kilowatts
            Divide by int, float, or Decimal.
        float
            Divide by Kilowatts
        """
        if isinstance(other, (int, float)):
            return type(self)(self.value / other)

        if isinstance(other, Decimal):
            return type(self)(self.value / float(other))

        if isinstance(other, Kilowatts):
            return self.value / other.value

        return NotImplemented


@total_ordering
class KilowattHours:
    """Energy in kilowatt-hours (kWh)."""

    def __init__(self, value: Union[str, int, float, Decimal, Self]) -> None:
        """Initialize a KilowattHours instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  Self
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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, int, float, Decimal, KilowattHours)):
            return self.value == KilowattHours(other).value
        return NotImplemented

    def __lt__(self, other: Union[str, int, float, Decimal, Self]) -> bool:
        return self.value < KilowattHours(other).value

    def __neg__(self) -> Self:
        return type(self)(-self.value)

    def __abs__(self):
        return type(self)(self.value if self.value >= 0 else -self.value)

    def __round__(self, ndigits: int = 0):
        return type(self)(round(self.value, ndigits))

    def __add__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value + KilowattHours(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value += KilowattHours(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value - KilowattHours(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value -= KilowattHours(other).value
        return self

    @overload
    def __mul__(self, other: Union[int, float, Decimal]) -> Self: ...

    @overload
    def __mul__(self, other: 'DollarsPerKilowattHour') -> 'Dollars': ...

    def __mul__(
        self, other: Union[int, float, Decimal, 'DollarsPerKilowattHour']
    ) -> Union['Dollars', Self]:
        if isinstance(other, (int, float, Decimal)):
            return type(self)(self.value * Decimal(other))

        if isinstance(other, DollarsPerKilowattHour):
            return Dollars(Decimal(self.value) * other.value)

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal]) -> Self:  # type: ignore[misc]
        self.value = self.__mul__(other).value
        return self

    @overload
    def __truediv__(self, other: Self) -> Decimal: ...

    @overload
    def __truediv__(self, other: Union[int, float, Decimal]) -> Self: ...

    def __truediv__(self, other: Union[int, float, Decimal, Self]) -> Union[Decimal, Self]:
        if isinstance(other, (int, float, Decimal)):
            return type(self)(self.value / Decimal(other))

        if isinstance(other, KilowattHours):
            return self.value / other.value

        return NotImplemented


@total_ordering
class DollarsPerKilowatt:
    """Subscription (a.k.a demand) rate in dollars/kilowatt ($/kW)."""

    def __init__(self, value: Union[str, int, float, Decimal, Self]) -> None:
        """Initialize a DollarsPerKilowatt instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  Self
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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, int, float, Decimal, DollarsPerKilowatt)):
            return self.value == DollarsPerKilowatt(other).value
        return NotImplemented

    def __lt__(self, other: Union[str, int, float, Decimal, Self]) -> bool:
        return self.value < DollarsPerKilowatt(other).value

    def __neg__(self) -> Self:
        return type(self)(-self.value)

    def __add__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value + DollarsPerKilowatt(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value += DollarsPerKilowatt(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value - DollarsPerKilowatt(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value -= DollarsPerKilowatt(other).value
        return self

    @overload
    def __mul__(self, other: Union[int, float, Decimal]) -> Self: ...
    @overload
    def __mul__(self, other: Kilowatts) -> 'Dollars': ...
    def __mul__(self, other: object) -> object:
        if isinstance(other, (int, float, Decimal)):
            return type(self)(self.value * Decimal(other))

        if isinstance(other, Kilowatts):
            return Dollars(self.value * Decimal(other.value))

        return NotImplemented

    __rmul__ = __mul__

    @overload
    def __imul__(self, other: Union[int, float, Decimal]) -> Self: ...
    @overload
    def __imul__(self, other: Kilowatts) -> 'Dollars': ...
    def __imul__(self, other: object) -> object:  # type: ignore[misc]
        if isinstance(other, (int, float, Decimal)):
            self.value *= Decimal(other)
            return self

        raise TypeError("In-place multiplication with Kilowatts is not supported")

    def __truediv__(self, other: Union[int, float, Decimal]) -> Kilowatts:
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
        value : str  |  int  |  float  |  Decimal  |  Self
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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, int, float, Decimal, DollarsPerKilowattHour)):
            return self.value == DollarsPerKilowattHour(other).value
        return NotImplemented

    def __lt__(self, other: Union[str, int, float, Decimal, Self]) -> bool:
        return self.value < DollarsPerKilowattHour(other).value

    def __neg__(self) -> Self:
        return type(self)(-self.value)

    def __add__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value + DollarsPerKilowattHour(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value += DollarsPerKilowattHour(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value - DollarsPerKilowattHour(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value -= DollarsPerKilowattHour(other).value
        return self

    @overload
    def __mul__(self, other: Union[int, float, Decimal]) -> Self: ...
    @overload
    def __mul__(self, other: KilowattHours) -> 'Dollars': ...
    def __mul__(self, other: object) -> object:
        if isinstance(other, (int, float, Decimal)):
            return type(self)(self.value * Decimal(other))

        if isinstance(other, KilowattHours):
            return Dollars(self.value * other.value)

        return NotImplemented

    __rmul__ = __mul__

    @overload
    def __imul__(self, other: Union[int, float, Decimal]) -> Self: ...
    @overload
    def __imul__(self, other: KilowattHours) -> 'Dollars': ...
    def __imul__(self, other: object) -> object:  # type: ignore[misc]
        if isinstance(other, (int, float, Decimal)):
            self.value *= Decimal(other)
            return self

        raise TypeError("In-place multiplication with KilowattHours is not supported")

    def __truediv__(self, other: Union[int, float, Decimal]) -> Self:
        if isinstance(other, (int, float)):
            return type(self)(self.value / Decimal(other))

        if isinstance(other, Decimal):
            return type(self)(self.value / other)

        return NotImplemented


@total_ordering
class Dollars:
    """Charges/credits in dollars."""

    def __init__(self, value: Union[str, int, float, Decimal, Self]) -> None:
        """Initialize a Dollars instance.

        Parameters
        ----------
        value : str  |  int  |  float  |  Decimal  |  Self
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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, int, float, Decimal, Dollars)):
            return self.value == Dollars(other).value
        return NotImplemented

    def __lt__(self, other: Union[str, int, float, Decimal, Self]) -> bool:
        return self.value < Dollars(other).value

    def __neg__(self) -> Self:
        return type(self)(-self.value)

    def __abs__(self) -> Self:
        return type(self)(self.value if self.value >= 0 else -self.value)

    def __add__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value + Dollars(other).value)

    def __radd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__add__(other)

    def __iadd__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value += Dollars(other).value
        return self

    def __sub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return type(self)(self.value - Dollars(other).value)

    def __rsub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        return self.__sub__(other)

    def __isub__(self, other: Union[str, int, float, Decimal, Self]) -> Self:
        self.value -= Dollars(other).value
        return self

    def __mul__(self, other: Union[int, float, Decimal, Percent]) -> Self:
        if isinstance(other, (int, Decimal, Percent)):
            return type(self)(self.value * other)

        if isinstance(other, float):
            return type(self)(float(self.value) * other)

        return NotImplemented

    __rmul__ = __mul__

    def __imul__(self, other: Union[int, float, Decimal, Percent]) -> Self:
        self.value = self.__mul__(other).value
        return self

    @overload
    def __truediv__(self, other: Self) -> Decimal: ...

    @overload
    def __truediv__(self, other: Union[int, float]) -> Self: ...

    @overload
    def __truediv__(self, other: Kilowatts) -> DollarsPerKilowatt: ...

    @overload
    def __truediv__(self, other: KilowattHours) -> DollarsPerKilowattHour: ...

    @overload
    def __truediv__(self, other: DollarsPerKilowatt) -> Kilowatts: ...

    @overload
    def __truediv__(self, other: DollarsPerKilowattHour) -> KilowattHours: ...

    def __truediv__(
        self,
        other: Union[
            int, float, Kilowatts, KilowattHours, DollarsPerKilowatt, DollarsPerKilowattHour, Self
        ],
    ) -> Union[Decimal, DollarsPerKilowatt, DollarsPerKilowattHour, Kilowatts, KilowattHours, Self]:
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
        Kilowatts
            Divide by DollarsPerKilowatt.
        KilowattHours
            Divide by DollarsPerKilowattHour.
        Decimal
            Divide by Dollars

        Raises
        ------
        TypeError
            Invalid parameter type.
        """
        if isinstance(other, int):
            return type(self)(self.value / other)

        if isinstance(other, float):
            return type(self)(float(self.value) / other)

        if isinstance(other, Dollars):
            return Decimal(self.value / other.value)

        if isinstance(other, Kilowatts):
            return DollarsPerKilowatt(self.value / Decimal(other.value))

        if isinstance(other, KilowattHours):
            return DollarsPerKilowattHour(self.value / other.value)

        if isinstance(other, DollarsPerKilowatt):
            return Kilowatts(self.value / other.value)

        if isinstance(other, DollarsPerKilowattHour):
            return KilowattHours(self.value / other.value)

        return NotImplemented
