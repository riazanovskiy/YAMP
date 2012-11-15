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

import enchant
import mp3utils
import pytils

import onlinedata
from log import logger
from onlinedata import OnlineData
from tags import open_tag
from misc import filesize, is_all_ascii, levenshtein
from errors import DoublecheckEncodingException


languages = ['en_US', 'de_DE', 'ru_RU']  # FIXME: add french
enchant_dictionaries = [enchant.Dict(lang) for lang in languages]


def is_music_file(filename):
    return filename.endswith('.mp3') and filesize(filename)


def get_yn_promt(promt):
    ans = input(promt)
    while ans not in ['y', 'n', '']:
        ans = input(promt)
    return ans == 'y'


def measure_spelling(words, strict=True):
    _words = re.sub('[][._/(:;\)-]', ' ', words).split()
    spelling = 0.0
    for word in _words:
        if not word.isdigit():
            for d in enchant_dictionaries:
                if d.check(word):
                    spelling += 1
                    break
                elif not strict and len(d.suggest(word)) > 0:
                    spelling += 0.5
                    break

    spelling /= len(_words)
    # print('Spelling for', words, 'is', spelling)

    return spelling


def get_translit(words):
    return ' '.join(pytils.translit.detranslify(i) for i in re.sub('[._/-]', ' ', words).split())


def improve_encoding(request):
    if is_all_ascii(request):
        return request
    attepmts = [('cp1252', 'cp1251'), ('cp1251', 'cp1252')]
    result = request
    spelling = measure_spelling(request)
    for dst, src in attepmts:
        try:
            suggest = request.encode(dst).decode(src)
            quality = measure_spelling(suggest)
            if quality > spelling:
                result = suggest
        except:
            continue

    # if spelling < 0.1 and result == request:
        # result = get_translit(request)
        # if measure_spelling(result, False) > 0.99:
            # print('Detranslifyed:', result)
            # exc = DoublecheckEncodingException()
            # exc.improved = result
            # raise exc

    return result


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

    def pretty_print(self, only_good=True):
        self.cursor.execute('select artist, album, title from songs')
        for (artist, album, title) in sorted(self.cursor):
            print('{} -- {} -- {}'.format(artist, album, title))

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
                print('Lookup for', i)
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
                self.cursor.execute('update or ignore songs set {}=? where {}=?'.format(field, field),
                                    (new, old))
                self.cursor.execute('delete from songs where {}=?'.format(field), (old,))

        self.sql_connection.commit()

    def print_artists(self):
        self.cursor.execute('select distinct artist from songs')
        for name, in self.cursor:
            print(name)

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
        print(len(filenames))
        filenames = set(filenames)
        print(len(filenames))
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

    def deal_with_track_numbers(self):
        pass
        # self.cursor.execute('select distinct album, artist from songs')
        # albums = list(self.cursor)
        # pprint(albums)

    def improve_metadata(self):
        self.remove_extensions_from_tracks()
        # self.remove_common_in_dir()
        # self.remove_common()
        self.deal_with_track_numbers()

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
        print(artist)
        self.cursor.execute('select title from songs where artist=?', (artist,))
        known_tracks = set([i for i, in self.cursor])
        pprint(known_tracks)
        suggestions = self.online.get_tracks_for_artist(artist)
        print(len(suggestions))
        suggestions = [i for i in suggestions if i[0] not in known_tracks]
        print(len(suggestions))
        suggestions = [i for i in suggestions if not any(j in i for j in known_tracks)]
        print(len(suggestions))
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
        artists = {i: re.sub(' +', ' ', re.sub('[][._/(:;\)-]', ' ', i.upper())) for i, in artists if i}
        matches = {i: 0 for i in artists.values()}
        for i in artists.values():
            for j in artists.values():
                if (1.0 - levenshtein(i, j) / max(len(i), len(j))) > 0.9:
                    print(i, j, 1.0 - levenshtein(i, j) / max(len(i), len(j)))
                    matches[i] += 1
                    matches[j] += 1

        to_correct = [i for i in matches if matches[i] > 2]

        for i in to_correct:
            print(i, matches[i])

        for artist in to_correct:
            improved = self.online.generic_search('artist', artist)
            print('REPLACING', artist, 'WITH', improved)
            for i, j in artists.items():
                if j == artist:
                    self.cursor.execute('update or ignore songs set artist=? where artist=?',
                                        (improved, i))
                    self.cursor.execute('delete from songs where artist=?', (i,))
        self.sql_connection.commit()

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
    database.pretty_print()
    # database.add_tracks_for_artist('Pink Floyd', count=30)
    # database.add_tracks_for_artist('Сплин')
    database.pretty_print()
