# -*- coding: utf-8 -*-
# -*- test-case-name: pytils.test.test_utils -*-
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
# from __future__ import print_function, absolute_import, division, unicode_literals
"""
Misc utils for internal use
"""
from pytils.third import six
from decimal import Decimal
from pytils.third.aspn426123 import takes
from pytils.third.aspn426123 import optional


@takes((tuple, list) + six.string_types, (int, ))
def check_length(value, length):
    """
    Checks length of value

    @param value: value to check
    @type value: C{str}

    @param length: length checking for
    @type length: C{int}

    @return: None when check successful

    @raise ValueError: check failed
    """
    _length = len(value)
    if _length != length:
        raise ValueError("length must be %d, not %d" % \
                         (length, _length))


@takes((float,Decimal) + six.integer_types, optional(bool), strict=optional(bool))
def check_positive(value, strict=False):
    """
    Checks if variable is positive

    @param value: value to check
    @type value: C{int}, C{long}, C{float} or C{Decimal}

    @return: None when check successful

    @raise ValueError: check failed
    """
    if not strict and value < 0:
        raise ValueError("Value must be positive or zero, not %s" % str(value))
    if strict and value <= 0:
        raise ValueError("Value must be positive, not %s" % str(value))


@takes(six.text_type, optional(six.text_type), sep=optional(six.text_type))
def split_values(ustring, sep=','):
    """
    Splits unicode string with separator C{sep},
    but skips escaped separator.

    @param ustring: string to split
    @type ustring: C{unicode}

    @param sep: separator (default to ',')
    @type sep: C{unicode}

    @return: tuple of splitted elements
    """
    assert isinstance(ustring, six.text_type), "uvalue must be unicode, not %s" % type(ustring)
    # unicode have special mark symbol 0xffff which cannot be used in a regular text,
    # so we use it to mark a place where escaped column was
    ustring_marked = ustring.replace('\,', '\uffff')
    items = tuple([i.strip().replace('\uffff', ',') for i in ustring_marked.split(sep)])
    return items
