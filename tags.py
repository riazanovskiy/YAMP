# -*- coding: utf-8 -*-
# print ('Started ' + __name__)
from stagger import *
from stagger.id3 import *
from stagger.tags import *
from stagger.id3v1 import *


def open_tag(filename):
    '''Returns a stagger Tag object with tags from filename'''
    tag = None
    try:
        tag = read_tag(filename)
    except NoTagError:
        tag = stagger.tags.Tag23()
        tag._filename = filename
        try:
            tag.write()
        except:
            pass
    return tag
