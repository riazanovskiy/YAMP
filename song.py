# -*- coding: utf-8 -*-
print ('Started ' + __name__)
import tags
import os


class Song:
    def __init__(self, filename=None):
        self.confirmed = None
        self.filename = None
        if filename:
            self.load(filename)

    def load(self, filename):
        self.filename = os.path.normpath(filename)
        self.tags = tags.open_tag(self.filename)
        self.tags.write()

    def __str__(self):
        return '#{number} {artist} - {album} - {title}'.format(album=self.tags.album, number=self.tags.track, title=self.tags.title, artist=self.tags.artist)

    def __repr__(self):
        # print('\n'.join(self.tags.frames()))
        return str(self)  # '\n'.join((str(i) for i in self.tags.frames())) + '\n' * 2

    def __lt__(self, other):
        self_list = [self.tags.artist, self.tags.album, self.tags.track, self.tags.title]
        other_list = [other.tags.artist, other.tags.album, other.tags.track, other.tags.title]
        for i in zip(self_list, other_list):
            if i[0] != i[1]:
                return i[0] < i[1]

        return False

    def __eq__(self, other):
        self_list = [self.tags.artist, self.tags.album, self.tags.track, self.tags.title]
        other_list = [other.tags.artist, other.tags.album, other.tags.track, other.tags.title]
        for i in zip(self_list, other_list):
            if i[0] != i[1]:
                return False

        return True

    def __hash__(self):
        return hash(str(self))
