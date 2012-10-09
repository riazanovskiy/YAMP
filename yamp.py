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


def get_yn_promt(promt):
    ans = input(promt)
    while ans not in ['y', 'n', '']:
        ans = input(promt)
    return ans == 'y'


def verify_dir(name):
    if not os.path.isdir(name):
        os.makedirs(name)


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
        self.cursor.execute('create table if not exists artists (name text unique)')
        self.cursor.execute('create table if not exists albums (title text, '
                            ' artist text, confirmed boolean default 0, '
                            ' unique (artist, title))')

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
        self.cursor.execute('insert or ignore into artists (name) '
                            'select distinct artist from songs')
        self.cursor.execute('insert or ignore into albums (title, artist) '
                            'select distinct album, artist from songs')
        self.sql_connection.commit()

    def writeout(self):
        self.cursor.execute('select track, artist, album, title, filename, '
                            ' from songs where has_file=1')
        for (track, artist, album, title, filename) in self.cursor:
            tag = open_tag(filename)
            tag._frames.clear()
            tag.track = track
            tag.artist = artist
            tag.album = album
            tag.title = title
            tag.write()

    def pretty_print(self, only_good=True):
        self.cursor.execute('select artist, album, title from songs')
        data = sorted(self.cursor.fetchall())
        for (artist, album, title) in data:
            print('{} -- {} -- {}'.format(artist, album, title))

    def print_tags(self):
        self.cursor.execute('select filename from songs')
        for i in self.cursor:
            print('\n'.join((map(repr, open_tag(i[0]).frames()))) + '\n')

    def correct_artists(self):
        self.cursor.execute('select name from artists')
        artists = {i: i for (i,) in self.cursor}

        for artist in artists:
            artists[artist] = improve_encoding(artist)

        case_mapping = defaultdict(lambda: [])
        for i in artists.values():
            case_mapping[i.upper()].append(i)

        cases = dict()
        for i in case_mapping:
            if len(case_mapping[i]) == 1:
                cases[i] = case_mapping[i][0]
            else:
                cases[i] = self.online.search_artist(i)

        for orig, artist in artists.items():
            artists[orig] = cases[artist.upper()]

        for old, new in artists.items():
            if old != new:
                self.cursor.execute('update songs set artist=? where artist=?',
                                    (new, old))
                self.cursor.execute('update or ignore artists set name=? where name=?',
                                    (new, old))
        self.sql_connection.commit()

    def correct_albums(self):
        ask = lru_cache()(lambda x, y: input(x))
        ask_yn = lru_cache()(get_yn_promt)
        self.cursor.execute('select artist, title from albums where confirmed=0')
        albums = self.cursor.fetchall()
        self.cursor.execute('select title from albums')
        self.albums = [i for (i,) in self.cursor.fetchall()]
        update_songs = []
        for artist, title in albums:
            confirmed = 1
            found = title
            if not ask_yn('Is {} -- {} correct? '.format(artist, title)):
                found = self.search(title, 'album')
                if not ask_yn('Is {} correct? '.format(found)):
                    found = self.search(title, 'album', incorrect=True)
                    if not ask_yn('Is {} correct? '.format(found)):
                        promt = ask('Enter correct album (empty to leave as is): ', found)
                        if promt == '':
                            confirmed = 0
                        found = promt or found

            self.cursor.execute('delete from albums where title=? and artist=?',
                                (title, artist))
            self.cursor.execute('insert or ignore into albums (artist, title, confirmed) '
                                ' values (?, ?, ?)', (artist, found, confirmed))

            if found != title:
                self.mapping[title] = found
                update_songs.append((found, title, artist))

        self.cursor.executemany('update or ignore songs set album=? '
                                ' where album=? and artist=?',
                                 update_songs)
        self.dump_mapping()
        self.sql_connection.commit()

    def correct_tracks(self):
        ask = lru_cache()(lambda x, y: input(x))
        ask_yn = lru_cache()(get_yn_promt)
        self.cursor.execute('select artist, title from albums')
        albums_titles = self.cursor.fetchall()
        albums = []
        for artist, title in albums_titles:
            self.cursor.execute('select title from songs where album=? '
                                ' and artist=? and confirmed=0', (title, artist))
            tracks = self.cursor.fetchall()
            if tracks:
                albums.append({'artist': artist, 'title': title,
                               'list': [i for i, in tracks]})

        for album in albums:
            confirmed = 1
            print (album['title'], ' -- ', album['artist'])
            for i in album['list']:
                print('\t', i)
            if get_yn_promt('Are these all correct? '):
                self.cursor.execute('update or ignore songs set confirmed=1 '
                                    ' where artist=? and album=?',
                                    (album['artist'], album['title']))
            else:
                for i in album['list']:
                    found = i
                    confirmed = 1
                    if not ask_yn('Is {} correct? '.format(found)):
                        found = self.search((album['artist'], found), 'track')
                        if not ask_yn('Is {} correct? '.format(found)):
                            found = self.search((album['artist'], found),
                                                'track', incorrect=True)
                            if not ask_yn('Is {} correct? '.format(found)):
                                promt = ask('Enter correct track (empty to leave as is): ', found)
                                if promt == '':
                                    confirmed = 0
                                found = promt or found
                    if found != i:
                        self.mapping[i] = found
                    self.cursor.execute('update or ignore songs set confirmed=?, title=?'
                                        ' where artist=? and album=? and title=?',
                                        (confirmed, found, album['artist'],
                                         album['title'], i))
        self.dump_mapping()
        self.sql_connection.commit()

    def print_artists(self):
        self.cursor.execute('select * from artists')
        for name in self.cursor:
            print(name)

if __name__ == '__main__':
    database = Database('/home/dani/yamp')
    database.import_folder('/home/dani/tmp_')
    # database.import_folder('/home/dani/Music')
    print('All imported')
    database.print_artists()
    database.pretty_print()

    database.correct_artists()
    # database.correct_albums()
    # database.correct_tracks()
    database.print_artists()
    database.pretty_print()

# database.move_files()
# database.user_control()
# database.correct_tags()
# database.writeout()
