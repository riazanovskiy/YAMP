# -*- coding: utf-8 -*-
print ('Started ' + __name__)
import os
from log import logger
import shutil
import sqlite3
from tags import open_tag
from functools import lru_cache
import difflib
import enchant
from collections import defaultdict
from onlinedata import OnlineData

CMD_CHAR = '$' if os.name == 'nt' else '>'

languages = ['en_US', 'de_DE', 'ru_RU']  # FIXME add french
enchant_dictionaries = [enchant.Dict(lang) for lang in languages]


def safe_print(text):
    try:
        print (text)
    except:
        pass


def filesize(file):
    return os.stat(file).st_size


def is_music_file(filename):
    return filename.endswith('.mp3') and filesize(filename)


def valid_filename(filename):
    invalid = frozenset('*”"/\[]:;|=,')
    return ''.join('-' if i in invalid else i for i in filename)


def verify_dir(name):
    if not os.path.isdir(name):
        os.makedirs(name)


def get_yn_promt(promt):
    ans = input(promt)
    while ans not in ['y', 'n', '']:
        ans = input(promt)
    return ans == 'y'


def is_all_ascii(data):
    try:
        data.encode('ascii')
    except UnicodeEncodeError:
        return False
    else:
        return True


def measure_spelling(words):
    words = words.split()
    spelling = 0
    for word in words:
        for d in enchant_dictionaries:
            if d.check(word):
                spelling += 1
                break
    return spelling / len(words)


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
                            ' has_file boolean, confirmed boolean, '
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
                bitrate = duration = 0
                self.cursor.execute('insert or ignore into songs (track, artist, album,'
                                    ' title, bitrate, duration, filename, has_file, '
                                    ' confirmed)'
                                    'values (?, ?, ?, ?, ?, ?, ?, 1, 0)', (track,
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
        self.cursor.execute('select filename from songs')
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
            data[i] = improve_encoding(i)

        case_mapping = defaultdict(lambda: [])
        for i in data.values():
            case_mapping[i.upper()].append(i)

        cases = {}
        for i in case_mapping:
            if (len(case_mapping[i]) > 1 or case_mapping[i][0].isupper()
                or case_mapping[i][0].islower()):
                print('Lookup for', i)
                cases[i] = self.online.generic_search(what, i)
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

if __name__ == '__main__':
    database = Database('/home/dani/yamp')
    # database.import_folder('/home/dani/tmp_')
    # database.import_folder('/home/dani/Music')
    print('All imported')
    database.print_artists()
    database.pretty_print()

    print('Starting')
    database.generic_correction('artist')
    print('Aritsts done')
    database.generic_correction('album')
    print('Albums done')
    database.generic_correction('track')
    database.print_artists()
    database.pretty_print()

# database.move_files()
# database.user_control()
# database.correct_tags()
# database.writeout()
