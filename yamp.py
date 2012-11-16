# -*- coding: utf-8 -*-
# print ('Started ' + __name__)
import os
import shutil
import sqlite3
import difflib
import re
import random
import string
from functools import lru_cache
from collections import defaultdict
from pprint import pprint

import mp3utils

import onlinedata
from log import logger
from onlinedata import OnlineData
from tags import open_tag
from misc import filesize, is_all_ascii, levenshtein, normalcase, improve_encoding
from errors import DoublecheckEncodingException


def is_music_file(filename):
    return filename.endswith('.mp3') and filesize(filename)


def get_yn_promt(promt):
    ans = input(promt)
    while ans not in ['y', 'n', '']:
        ans = input(promt)
    return ans == 'y'


class Database:
    def __init__(self, path):
        self.online = OnlineData()
        self.path = os.path.abspath(path)
        self.datapath = os.path.join(path, 'database')
        self.sql_connection = sqlite3.connect(self.datapath)
        self.cursor = self.sql_connection.cursor()
        self.cursor.execute('create table if not exists songs (track int,'
                            ' artist text, album text, title text, bitrate int,'
                            ' duration int, filename text unique,'
                            ' has_file boolean, '
                            ' mbid text, '
                            # ' artist_as_online boolean, '
                            ' album_as_online boolean, '
                            # ' title_as_online boolean,'
                            ' grooveshark_id int, '
                            ' unique(artist, title, album))')

        self.cursor.execute('create unique index if not exists songsindex '
                            'ON songs(artist, title, album, filename)')

    def move_files(self):
        self.cursor.execute('select track, artist, album, title, filename from songs')
        moved = []
        for track, artist, album, title, old_filename in self.cursor:
            if not old_filename.startswith('NOFILE') and os.path.exists(old_filename):
                folder_name = os.path.join(self.path, valid_filename(artist),
                                           valid_filename(album))
                filename = os.path.join(folder_name,
                    valid_filename('{track:0=2} {title}.mp3'.format(track=track,
                                                                    title=title)))
                if old_filename != filename:
                    verify_dir(folder_name)
                    moved.append((shutil.copy(old_filename, filename), old_filename))

        self.cursor.executemany('update songs set filename=? where filename=?',
                                moved)
        self.sql_connection.commit()

    def import_folder(self, folder):
        for curr, dirs, files in os.walk(folder):
            for file in (os.path.join(curr, i) for i in files if is_music_file(os.path.join(curr, i))):
                tags = open_tag(file)

                track = tags.track
                artist = tags.artist.strip()
                album = tags.album.strip()
                title = tags.title.strip()
                # FIXME
                duration = 0
                try:
                    bitrate = mp3utils.mp3info(file)['BITRATE']
                except:
                    bitrate = 0

                self.cursor.execute('insert or ignore into songs (track, artist, album,'
                                    ' title, bitrate, duration, filename, has_file)'
                                    'values (?, ?, ?, ?, ?, ?, ?, 1)', (track,
                                    artist, album, title, bitrate, duration,
                                    file))
        self.sql_connection.commit()

    def writeout(self):
        self.cursor.execute('select track, artist, album, title, filename, '
                            ' from songs where has_file=1')
        for (track, artist, album, title, filename) in self.cursor:
            tag = open_tag(filename)
            tag._frames.clear()
            tag.track, tag.artist, tag.album, tag.title = track, artist, album, title
            tag.write()

    def pretty_print(self, artist=None, album=None):
        if artist:
            print(artist)
            self.cursor.execute('select distinct album from songs where artist=?', (artist,))
            for i, in self.cursor:
                print('\t', i)
        elif album:
            print(album, 'by', self.get_artist_of_album(album))
            self.cursor.execute('select track, title from songs where album=?', (album,))
            for track, title in sorted(self.cursor):
                print('#' + str(track), title)
        else:
            self.cursor.execute('select artist, album, track, title from songs')
            for (artist, album, track, title) in sorted(self.cursor):
                print('{} -- {} -- #{} {}'.format(artist, album, track, title))

    def print_tags(self):
        self.cursor.execute('select filename from songs where has_file=1')
        for i in self.cursor:
            print('\n'.join((map(repr, open_tag(i[0]).frames()))) + '\n')

    def generic_correction(self, what):
        try:
            assert (what in ['album', 'artist', 'track'])
        except AssertionError:
            print(what)
            raise
        field = what if what != 'track' else 'title'
        self.cursor.execute('select distinct {} from songs'.format(field))
        data = {i: i for (i,) in self.cursor}

        for i in data:
            try:
                data[i] = improve_encoding(i)
            except DoublecheckEncodingException as exc:
                data[i] = self.online.generic_search(what, exc.improved)

        case_mapping = defaultdict(lambda: [])
        for i in data.values():
            case_mapping[i.upper()].append(i)

        cases = {}
        for i in case_mapping:
            if (len(case_mapping[i]) > 1 or case_mapping[i][0].isupper()
                or case_mapping[i][0].islower()):
                try:
                    cases[i] = self.online.generic_search(what, i)
                    print(cases[i])
                except onlinedata.NotFoundOnline:
                    pass
            else:
                cases[i] = case_mapping[i][0]

        for old, new in data.items():
            data[old] = cases[new.upper()]

        for old, new in data.items():
            if old != new:
                print('REPLACING', old, 'WITH', new)
                self.cursor.execute('update or ignore songs set {}=? where {}=?'.format(field, field),
                                    (new, old))
                self.cursor.execute('delete from songs where {}=?'.format(field), (old,))

        self.sql_connection.commit()

    def remove_extensions_from_tracks(self):
        self.cursor.execute('select distinct title from songs')
        data = {i: i for (i,) in self.cursor}
        to_remove = ['.mp3', '.MP3', 'mp3', 'MP3']
        for i in data:
            for j in to_remove:
                if j in i:
                    data[i].replace(j, '')
                    break
        for i, j in data.items():
            if i != j:
                self.cursor.execute('update songs set title=? where title=?',
                                    (j, i))
        self.sql_connection.commit()

    def remove_by_list(self, tracks, what):
        for i in tracks:
            updated = i.replace(what, '')
            if updated != i:
                print('REPLACING', i, 'WITH', updated)
                self.cursor.execute('update songs set title=? where title=?',
                                    (updated, i))

    def remove_common_in_dir(self):
        self.cursor.execute('select filename from songs')
        filenames = [os.path.normpath(os.path.split(i)[0]) for i, in self.cursor]
        filenames = set(filenames)
        for directory in filenames:
            self.cursor.execute("select title from songs where filename like ?",
                                 (directory + '%',))
            tracks = [i for i, in self.cursor]
            if len(tracks) > 2:  # FIXME
                common = longest_common_substring(tracks)
                if common:
                    if all(i.startswith(common) for i in tracks):
                        self.remove_by_list(tracks, common)
            self.cursor.execute('select title from songs where filename like ?',
                                 (directory + '%',))
            tracks = [i for i, in self.cursor]
            if len(tracks) > 2:  # FIXME
                common = longest_common_substring(tracks)
                if common:
                    if all(i.endswith(common) for i in tracks):
                        self.remove_by_list(tracks, common)

    def remove_common(self):
        self.cursor.execute('select distinct album from songs')
        albums = list(self.cursor)
        for album in albums:
            self.cursor.execute('select title from songs where album=?', album)
            tracks = [i for i, in self.cursor]
            if len(tracks) > 2:  # FIXME
                common = longest_common_substring(tracks)
                if common:
                    if all(i.startswith(common) for i in tracks):
                        for i in tracks:
                            self.remove_by_list(tracks, common)

            self.cursor.execute('select title from songs where album=?', album)
            tracks = [i for i, in self.cursor]
            if len(tracks) > 2:  # FIXME
                common = longest_common_substring(tracks)
                if common:
                    if all(i.endswith(common) for i in tracks):
                        for i in tracks:
                            self.remove_by_list(tracks, common)

    def improve_metadata(self):
        self.remove_extensions_from_tracks()
        # self.remove_common_in_dir()
        # self.remove_common()

    def correct_artist(self, artist):
        improved = self.online.generic_search('artist', artist)
        if improved != artist:
            print('REPLACING', artist, 'WITH', improved)
            self.cursor.execute('select distinct artist from songs')
            artists = list(self.cursor)
            artists = {i: re.sub('[][._/(:;\)-]', ' ', i.upper()) for i, in artists if i}
            query = re.sub('[][._/(:;\)-]', ' ', artist.upper())
            for i, j in artists.items():
                if j == query:
                    self.cursor.execute('update or ignore songs set artist=? where artist=?',
                                        (improved, i))
                    self.cursor.execute('delete from songs where artist=?', (i,))
        return improved

    def add_tracks_for_artist(self, artist, count=20):
        artist = self.correct_artist(artist)
        self.cursor.execute('select title from songs where artist=?', (artist,))
        known_tracks = set([i for i, in self.cursor])
        suggestions = self.online.get_tracks_for_artist(artist)
        suggestions = [i for i in suggestions if i[0] not in known_tracks]
        suggestions = [i for i in suggestions if not any(j in i for j in known_tracks)]
        for song in suggestions[:count]:
            self.cursor.execute('insert or ignore into songs'
                                ' (artist, title, album, track, filename, has_file)'
                                ' values (?, ?, ?, ?, ?, 0)',
                                (artist, song[0], song[1], song[2], 'NOFILE' +
                                ''.join(random.choice(string.hexdigits) for x in range(16))))
        self.sql_connection.commit()

    def merge_artists(self):
        self.cursor.execute('select distinct artist from songs')
        artists = list(self.cursor)
        artists = {i: normalcase(i) for i, in artists if i}
        matches = {i: 0 for i in artists.values()}
        for i in artists.values():
            for j in artists.values():
                if (1.0 - levenshtein(i, j) / max(len(i), len(j))) > 0.9:
                    matches[i] += 1
                    matches[j] += 1

        to_correct = [i for i in matches if matches[i] > 2]

        for artist in to_correct:
            improved = self.online.generic_search('artist', artist)
            print('REPLACING', artist, 'WITH', improved)
            for i, j in artists.items():
                if j == artist:
                    self.cursor.execute('update or ignore songs set artist=? where artist=?',
                                        (improved, i))
                    self.cursor.execute('delete from songs where artist=?', (i,))
        self.sql_connection.commit()

    def fill_album(self, artist, album):
        artist = self.correct_artist(artist)
        fetched_tracks = self.online.get_track_list(artist, album)
        for i in range(len(fetched_tracks)):
            if len(fetched_tracks[i]) < 2:
                fetched_tracks[i] = (fetched_tracks[i][0], 0)
        self.cursor.execute('select track, title from songs where artist=? and album=?',
                            (artist, album))
        known_tracks = sorted(self.cursor)
        for i in range(len(fetched_tracks)):
            for idx, song in known_tracks:
                if song == fetched_tracks[i][0]:
                    if i + 1 != idx:
                        print('Song', song, ': ', idx, ' -> ', i + 1)
                        self.cursor.execute('update songs set track=?, grooveshark_id=? '
                                            ' where title=? and artist=? and album=?',
                                            (i + 1, fetched_tracks[i][1], song, artist, album))
                    break
            else:
                self.cursor.execute('insert into songs (grooveshark_id, track, artist, album, '
                                                      ' title, filename, has_file) '
                                    'values (?, ?, ?, ?, ?, ?, 0) ',
                                    (fetched_tracks[i][1], i + 1, artist, album, fetched_tracks[i][0],
                                     'NOFILE' + ''.join(random.choice(string.hexdigits) for x in range(16))))
        self.sql_connection.commit()

    def get_artists_list(self):
        self.cursor.execute('select distinct artist from songs')
        return (i for i, in self.cursor if i)

    def get_albums_list(self, artist=None):
        if artist:
            self.cursor.execute('select distinct album from songs where artist=?',
                                (artist,))
        else:
            self.cursor.execute('select distinct album from songs')
        return (i for i, in self.cursor if i)

    def get_artist_of_album(self, album):
        self.cursor.execute('select artist from songs where album=?', (album,))
        artists = list(self.cursor)
        if artists:
            return artists[0][0]
        else:
            return self.online.artist_of_album(album)

if __name__ == '__main__':
    database = Database('/home/dani/yamp')
    # database.import_folder('/home/dani/tmp_')
    # database.import_folder('/home/dani/Music')
    # database.remove_extensions_from_tracks()
    # database.generic_correction('artist')
    # database.generic_correction('album')
    # database.generic_correction('track')

##########################################

    # database.improve_metadata()
    # database.pretty_print()
    # database.fill_album('Несчастный случай', 'Тоннель в конце света')
    # database.add_tracks_for_artist('Pink Floyd', count=30)
    # database.add_tracks_for_artist('Сплин')
    # database.pretty_print()
