"""evunits test suite."""
import unittest
from decimal import Decimal
from evunits import (
    Percent, SubscriptionMonths, Kilowatts, KilowattHours,
    DollarsPerKilowatt, DollarsPerKilowattHour, Dollars
)

# pylint: disable=missing-function-docstring

class TestPercent(unittest.TestCase):
    """Test suite for the Percent class."""
    def test_init_and_str(self):
        p = Percent(12.34)
        self.assertAlmostEqual(float(p), 0.1234)
        self.assertEqual(str(p.quantize(Decimal('0.01'))), "12.34%")
        self.assertEqual(repr(Percent('12.3')), "Percent(12.3)")
        self.assertEqual(f"{p:.3f}", "12.340")
    def test_quantize(self):
        p = Percent(12.3456)
        self.assertEqual(p.quantize(), Percent('12.346'))

class TestSubscriptionMonths(unittest.TestCase):
    """Test suite for the SubscriptionMonths class."""
    def test_repr(self):
        self.assertEqual(repr(SubscriptionMonths('.1234')), "SubscriptionMonths(0.1234)")

class TestKilowatts(unittest.TestCase):
    """Test suite for the Kilowatts class."""
    def test_init_and_str(self):
        k = Kilowatts("1,234.56")
        self.assertEqual(k.value, 1234.56)
        self.assertEqual(str(k), "1234.56")
        self.assertEqual(repr(k), "Kilowatts(1234.56)")
        self.assertEqual(float(k), 1234.56)
    def test_eq_lt(self):
        self.assertTrue(Kilowatts(1) == 1)
        self.assertTrue(Kilowatts(0) < 1)
        self.assertTrue(Kilowatts(1) > 0)
    def test_neg_add_sub_mul_div(self):
        k = Kilowatts(2)
        self.assertEqual(-k, Kilowatts(-2))
        self.assertEqual(k + 2, Kilowatts(4))
        self.assertEqual(2 + k, Kilowatts(4))
        k2 = Kilowatts(2)
        k2 += 2
        self.assertEqual(k2, Kilowatts(4))
        self.assertEqual(k - 1, Kilowatts(1))
        k3 = Kilowatts(2)
        k3 -= 1
        self.assertEqual(k3, Kilowatts(1))
        self.assertEqual(k * 2, Kilowatts(4))
        self.assertEqual(2 * k, Kilowatts(4))
        k4 = Kilowatts(2)
        k4 *= 2
        self.assertEqual(k4, Kilowatts(4))
        self.assertEqual(k / 2, Kilowatts(1))
        self.assertEqual(Kilowatts(1) / Kilowatts(2), 0.5)
    def test_percent_mul(self):
        self.assertEqual(Kilowatts(1) * Percent(50), Kilowatts(0.5))

class TestKilowattHours(unittest.TestCase):
    """Test suite for the KilowattHours class."""
    def test_init_and_str(self):
        kwh = KilowattHours("1,234.123456")
        self.assertEqual(kwh.value, Decimal("1234.123456"))
        self.assertEqual(str(kwh), "1234.123456")
        self.assertEqual(repr(kwh), "KilowattHours(1234.123456)")
        self.assertEqual(float(kwh), 1234.123456)
    def test_eq_lt(self):
        self.assertTrue(KilowattHours(1) == 1)
        self.assertTrue(KilowattHours(0) < 1)
        self.assertTrue(KilowattHours(1) > 0)
    def test_neg_add_sub_mul_div(self):
        k = KilowattHours(2)
        self.assertEqual(-k, KilowattHours(-2))
        self.assertEqual(k + 2, KilowattHours(4))
        self.assertEqual(2 + k, KilowattHours(4))
        k2 = KilowattHours(2)
        k2 += 2
        self.assertEqual(k2, KilowattHours(4))
        self.assertEqual(k - 1, KilowattHours(1))
        k3 = KilowattHours(2)
        k3 -= 1
        self.assertEqual(k3, KilowattHours(1))
        self.assertEqual(k * 2, KilowattHours(4))
        self.assertEqual(2 * k, KilowattHours(4))
        k4 = KilowattHours(2)
        k4 *= 2
        self.assertEqual(k4, KilowattHours(4))
        self.assertEqual(k / 2, KilowattHours(1))
        self.assertEqual(KilowattHours(1) / KilowattHours(2), Decimal("0.5"))
    def test_mul_with_rate(self):
        rate = DollarsPerKilowattHour(2)
        self.assertEqual(KilowattHours(2) * rate, Dollars(4))

class TestDollarsPerKilowatt(unittest.TestCase):
    """Test suite for the DollarsPerKilowatt class."""
    def test_init_and_str(self):
        dpk = DollarsPerKilowatt("1.12345")
        self.assertEqual(dpk.value, Decimal("1.12345"))
        self.assertEqual(str(dpk), "1.12345")
        self.assertEqual(repr(dpk), "DollarsPerKilowatt(1.12345)")
        self.assertEqual(float(dpk), 1.12345)
    def test_eq_lt(self):
        self.assertTrue(DollarsPerKilowatt(1) == 1)
        self.assertTrue(DollarsPerKilowatt(0) < 1)
        self.assertTrue(DollarsPerKilowatt(1) > 0)
    def test_neg_add_sub_mul_div(self):
        d = DollarsPerKilowatt(2)
        self.assertEqual(-d, DollarsPerKilowatt(-2))
        self.assertEqual(d + 2, DollarsPerKilowatt(4))
        self.assertEqual(2 + d, DollarsPerKilowatt(4))
        d2 = DollarsPerKilowatt(2)
        d2 += 2
        self.assertEqual(d2, DollarsPerKilowatt(4))
        self.assertEqual(d - 1, DollarsPerKilowatt(1))
        d3 = DollarsPerKilowatt(2)
        d3 -= 1
        self.assertEqual(d3, DollarsPerKilowatt(1))
        self.assertEqual(d * 2, DollarsPerKilowatt(4))
        self.assertEqual(2 * d, DollarsPerKilowatt(4))
        d4 = DollarsPerKilowatt(2)
        d4 *= 2
        self.assertEqual(d4, DollarsPerKilowatt(4))
        self.assertEqual(d / 2, Kilowatts(1))
    def test_mul_with_kw(self):
        self.assertEqual(DollarsPerKilowatt(2) * Kilowatts(2), Dollars(4))

class TestDollarsPerKilowattHour(unittest.TestCase):
    """Test suite for the DollarsPerKilowattHour class."""
    def test_init_and_str(self):
        dpkh = DollarsPerKilowattHour("1.12345")
        self.assertEqual(dpkh.value, Decimal("1.12345"))
        self.assertEqual(str(dpkh), "1.12345")
        self.assertEqual(repr(dpkh), "DollarsPerKilowattHour(1.12345)")
        self.assertEqual(float(dpkh), 1.12345)
        dpkh_neg = DollarsPerKilowattHour("(1.12345)")
        self.assertEqual(dpkh_neg.value, Decimal("-1.12345"))
        self.assertEqual(str(dpkh_neg), "-1.12345")
    def test_eq_lt(self):
        self.assertTrue(DollarsPerKilowattHour(1) == 1)
        self.assertTrue(DollarsPerKilowattHour(0) < 1)
        self.assertTrue(DollarsPerKilowattHour(1) > 0)
    def test_neg_add_sub_mul_div(self):
        d = DollarsPerKilowattHour(2)
        self.assertEqual(-d, DollarsPerKilowattHour(-2))
        self.assertEqual(d + 2, DollarsPerKilowattHour(4))
        self.assertEqual(2 + d, DollarsPerKilowattHour(4))
        d2 = DollarsPerKilowattHour(2)
        d2 += 2
        self.assertEqual(d2, DollarsPerKilowattHour(4))
        self.assertEqual(d - 1, DollarsPerKilowattHour(1))
        d3 = DollarsPerKilowattHour(2)
        d3 -= 1
        self.assertEqual(d3, DollarsPerKilowattHour(1))
        self.assertEqual(d * 2, DollarsPerKilowattHour(4))
        self.assertEqual(2 * d, DollarsPerKilowattHour(4))
        d4 = DollarsPerKilowattHour(2)
        d4 *= 2
        self.assertEqual(d4, DollarsPerKilowattHour(4))
        self.assertEqual(d / 2, DollarsPerKilowattHour(1))
    def test_mul_with_kwh(self):
        self.assertEqual(DollarsPerKilowattHour(2) * KilowattHours(2), Dollars(4))

class TestDollars(unittest.TestCase):
    """Test suite for the Dollars class."""
    def test_init_and_str(self):
        d = Dollars("1,234.56")
        self.assertEqual(d.value, Decimal("1234.56"))
        self.assertEqual(str(d), "1234.56")
        self.assertEqual(repr(d), "Dollars(1234.56)")
        self.assertEqual(float(d), 1234.56)
    def test_eq_lt(self):
        self.assertTrue(Dollars(1) == 1)
        self.assertTrue(Dollars(0) < 1)
        self.assertTrue(Dollars(1) > 0)
    def test_neg_abs_add_sub_mul_div(self):
        d = Dollars(2)
        self.assertEqual(-d, Dollars(-2))
        self.assertEqual(abs(Dollars(-2)), Dollars(2))
        self.assertEqual(d + 2, Dollars(4))
        self.assertEqual(2 + d, Dollars(4))
        d2 = Dollars(2)
        d2 += 2
        self.assertEqual(d2, Dollars(4))
        self.assertEqual(d - 1, Dollars(1))
        d3 = Dollars(2)
        d3 -= 1
        self.assertEqual(d3, Dollars(1))
        self.assertEqual(d * 2, Dollars(4))
        self.assertEqual(2 * d, Dollars(4))
        d4 = Dollars(2)
        d4 *= 2
        self.assertEqual(d4, Dollars(4))
        self.assertEqual(d / 2, Dollars(1))
        self.assertEqual(Dollars(1) / Dollars(2), Decimal("0.5"))
    def test_percent_mul(self):
        self.assertEqual(Dollars(1) * Percent(50), Dollars(0.5))
    def test_division_types(self):
        self.assertEqual(Dollars(1) / Kilowatts(2), DollarsPerKilowatt(0.5))
        self.assertEqual(Dollars(1) / KilowattHours(2), DollarsPerKilowattHour(0.5))
        self.assertEqual(Dollars(1) / DollarsPerKilowatt(2), Kilowatts(0.5))
        self.assertEqual(Dollars(1) / DollarsPerKilowattHour(2), KilowattHours(0.5))

if __name__ == '__main__':
    unittest.main()
