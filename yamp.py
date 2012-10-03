# -*- coding: utf-8 -*-
print ('Started ' + __name__)
import os
from log import logger
import shutil
import sqlite3
from tags import open_tag
import pylast
from functools import lru_cache
import difflib

CMD_CHAR = '$' if os.name == 'nt' else '>'


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


class Database:
    def __init__(self, path):
        self.network = pylast.LastFMNetwork('e494d3c2d1e99307336886c9e1f18af2',
                                            '989f1acfe251e590981d485ad9a82bd1')
        self.path = os.path.abspath(path)
        self.datapath = os.path.join(path, 'database')
        self.sql_connection = sqlite3.connect(self.datapath)
        self.cursor = self.sql_connection.cursor()
        self.cursor.execute('create table if not exists songs (track int,'
                            ' artist text, album text, title text, bitrate int,'
                            ' duration int, filename text unique,'
                            ' has_file boolean, confirmed boolean, '
                            ' unique(artist, title, album))')
        self.cursor.execute('create table if not exists artists (name text unique, '
                            ' confirmed boolean default 0)')
        self.cursor.execute('create table if not exists albums (title text, '
                            ' artist text, confirmed boolean default 0, '
                            ' unique (artist, title))')

        self.cursor.execute('create unique index if not exists songsindex '
                            'ON songs(artist, title, album, filename)')
        self.cursor.execute('create unique index if not exists artistsindex '
                            'ON artists(name, confirmed)')

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
        self.cursor.execute('select artist, title from songs')
        for (artist, title) in self.cursor:
            print('{} -- {}'.format(artist, title))

    def print_tags(self):
        self.cursor.execute('select filename from songs')
        for i in self.cursor:
            print('\n'.join((map(repr, open_tag(i[0]).frames()))) + '\n')

    @lru_cache()
    def search(self, request, what, incorrect=False):
        attepmts = [('utf-8', 'utf-8'), ('cp1252', 'cp1251'), ('utf-8', 'utf-8')]
        result = None
        assert (what in {'artist', 'album', 'track'})
        for dst, src in attepmts[incorrect:]:
            try:
                suggest = request.encode(dst).decode(src)
            except:
                continue
            try:
                if suggest != request:
                    local = difflib.get_close_matches(suggest, getattr(self, what + 's'),
                                                      1, 0.8)
                    if local:
                        result = local[0]
                        break
                search = getattr(self.network, 'search_for_' + what)(suggest)
                result = search.get_next_page()
                print('Result  \t', result)
                if result:
                    if what == 'artist':
                        result = result[0].get_name(properly_capitalized=True)
                    elif what == 'album':
                        result = result[0].get_title()
                    else:
                        raise Exception('Unimplemented!')
                    break
            except:
                pass
        return result or request

    def correct_artists(self):
        ask = lru_cache()(lambda x, y: input(x))
        ask_yn = lru_cache()(get_yn_promt)
        self.cursor.execute('select name from artists where confirmed=0')
        artists = [i for (i,) in self.cursor.fetchall()]
        self.cursor.execute('select name from artists')
        self.artists = [i for (i,) in self.cursor.fetchall()]
        update_songs = []
        for artist in artists:
            found = artist  # self.search(artist, 'artist')
            confirmed = 1
            if not ask_yn('Is {} correct? '.format(found)):
                found = self.search(found, 'artist', incorrect=True)
                if not ask_yn('Is {} correct? '.format(found)):
                    promt = ask('Enter correct artist (empty to leave as is): ', found)
                    if promt == '':
                        confirmed = 0
                    found = promt or found

            self.cursor.execute('delete from artists where name=?', (artist,))
            self.cursor.execute('insert or ignore into artists (name, confirmed) '
                                ' values (?, ?)', (found, confirmed))
            if found != artist:
                update_songs.append((found, artist))

        self.cursor.executemany('update or ignore songs set artist=? where artist=?',
                                 update_songs)
        self.cursor.executemany('update or ignore albums set artist=? where artist=?',
                                 update_songs)
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
            if not ask_yn('Is {} -- {} correct? '.format(artist, title)):
                found = self.search(title, 'album', incorrect=True)
                if not ask_yn('Is {} correct? '.format(found)):
                    promt = ask('Enter correct album (empty to leave as is): ', found)
                    if promt == '':
                        confirmed = 0
                    found = promt or found

            self.cursor.execute('delete from albums where title=?', (title,))
            self.cursor.execute('insert or ignore into albums (artist, title, confirmed) '
                                ' values (?, ?, ?)', (artist, title, confirmed))
            if found != artist:
                update_songs.append((found, title))

        self.cursor.executemany('update or ignore songs set album=? where album=?',
                                 update_songs)
        self.sql_connection.commit()

    def print_artists(self):
        self.cursor.execute('select * from artists')
        for name, confirmed in self.cursor:
            print(name, ['not', ''][confirmed], 'confirmed')

database = Database('/home/dani/yamp')
# database.import_folder('/home/dani/Music')
database.correct_artists()
database.correct_albums()
database.print_artists()
database.pretty_print()

# database.move_files()
# database.user_control()
# database.correct_tags()
# database.writeout()
