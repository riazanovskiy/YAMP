# -*- coding: utf-8 -*-
# pytils - russian-specific string utils
# Copyright (C) 2006-2009  Yury Yurevich
#
# http://pyobject.ru/projects/pytils/
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, version 2
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
"""
Unit-tests for pytils.utils
"""
from __future__ import print_function, absolute_import, division, unicode_literals

import unittest
from pytils.third import six
import pytils
import decimal

class ASPN426123TestCase(unittest.TestCase):
    """
    Test case for third-party library from ASPN cookbook recipe #426123

    This unit-test don't cover all code from recipe
    """

    def testTakesPositional(self):
        @pytils.utils.takes(int, six.string_types)
        def func(i, s):
            return i + len(s)

        self.assertEquals(func(2, 'var'), 5)
        self.assertEquals(func(2, 'var'), 5)
        self.assertRaises(pytils.err.InputParameterError, func, 2, 5)
        self.assertRaises(pytils.err.InputParameterError, func, 2, ('var',))
        self.assertRaises(pytils.err.InputParameterError, func, 'var', 5)

    def testTakesNamed(self):
        @pytils.utils.takes(int, s=six.text_type)
        def func(i, s):
            return i + len(s)

        self.assertEquals(func(2, s='var'), 5)
        self.assertEquals(func(2, s='var'), 5)
        self.assertRaises(pytils.err.InputParameterError, func, 2, 'var')
        self.assertRaises(pytils.err.InputParameterError, func, 2, 5)
        self.assertRaises(pytils.err.InputParameterError, func, 2, ('var',))
        self.assertRaises(pytils.err.InputParameterError, func, 'var', 5)

    def testTakesOptional(self):
        @pytils.utils.takes(int,
                            pytils.utils.optional(six.string_types),
                            s=pytils.utils.optional(six.string_types))
        def func(i, s=''):
            return i + len(s)

        self.assertEquals(func(2, 'var'), 5)
        self.assertEquals(func(2, s='var'), 5)
        self.assertEquals(func(2, s='var'), 5)
        self.assertRaises(pytils.err.InputParameterError, func, 2, 5)
        self.assertRaises(pytils.err.InputParameterError, func, 2, ('var',))
        self.assertRaises(pytils.err.InputParameterError, func, 'var', 5)

    def testTakesMultiplyTypesAndTupleOf(self):
        @pytils.utils.takes(six.integer_types,
                            pytils.utils.tuple_of(six.text_type))
        def func(i, t=tuple()):
            return i + sum(len(s) for s in t)

        self.assertEquals(func(2, ('var', 'var2')), 9)
        if not six.PY3:
            self.assertEquals(func(long(2), ('var', 'var2')), 9)
        self.assertEquals(func(2, t=('var', 'var2')), 9)
        self.assertEquals(func(2, t=('var', 'var2')), 9)
        self.assertRaises(pytils.err.InputParameterError, func, 2, (2, 5))



class ChecksTestCase(unittest.TestCase):
    """
    Test case for check_* utils
    """

    def testCheckLength(self):
        """
        Unit-test for pytils.utils.check_length
        """
        self.assertEquals(pytils.utils.check_length("var", 3), None)

        self.assertRaises(ValueError, pytils.utils.check_length, "var", 4)
        self.assertRaises(ValueError, pytils.utils.check_length, "var", 2)
        self.assertRaises(ValueError, pytils.utils.check_length, (1,2), 3)
        self.assertRaises(TypeError, pytils.utils.check_length, 5)

    def testCheckPositive(self):
        """
        Unit-test for pytils.utils.check_positive
        """
        self.assertEquals(pytils.utils.check_positive(0), None)
        self.assertEquals(pytils.utils.check_positive(1), None)
        self.assertEquals(pytils.utils.check_positive(1, False), None)
        self.assertEquals(pytils.utils.check_positive(1, strict=False), None)
        self.assertEquals(pytils.utils.check_positive(1, True), None)
        self.assertEquals(pytils.utils.check_positive(1, strict=True), None)
        self.assertEquals(pytils.utils.check_positive(decimal.Decimal("2.0")), None)
        self.assertEquals(pytils.utils.check_positive(2.0), None)

        self.assertRaises(ValueError, pytils.utils.check_positive, -2)
        self.assertRaises(ValueError, pytils.utils.check_positive, -2.0)
        self.assertRaises(ValueError, pytils.utils.check_positive, decimal.Decimal("-2.0"))
        self.assertRaises(ValueError, pytils.utils.check_positive, 0, True)


class SplitValuesTestCase(unittest.TestCase):

    def testClassicSplit(self):
        """
        Unit-test for pytils.utils.split_values, classic split
        """
        self.assertEquals(("Раз", "Два", "Три"), pytils.utils.split_values("Раз,Два,Три"))
        self.assertEquals(("Раз", "Два", "Три"), pytils.utils.split_values("Раз, Два,Три"))
        self.assertEquals(("Раз", "Два", "Три"), pytils.utils.split_values(" Раз,   Два, Три  "))
        self.assertEquals(("Раз", "Два", "Три"), pytils.utils.split_values(" Раз, \nДва,\n Три  "))

    def testEscapedSplit(self):
        """
        Unit-test for pytils.utils.split_values, split with escaping
        """
        self.assertEquals(("Раз,Два", "Три,Четыре", "Пять,Шесть"), pytils.utils.split_values("Раз\,Два,Три\,Четыре,Пять\,Шесть"))
        self.assertEquals(("Раз, Два", "Три", "Четыре"), pytils.utils.split_values("Раз\, Два, Три, Четыре"))

if __name__ == '__main__':
    unittest.main()
