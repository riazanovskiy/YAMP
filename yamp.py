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
        self.cursor.execute('create unique index if not exists songsindex '
                            'ON songs(artist, title, album, filename)')
        self.cursor.execute('create unique index if not exists artistsindex '
                            'ON artists(name, confirmed)')

    def move_files(self):
        self.cursor.execute('select track, artist, album, title, filename from songs')
        moved = []
        for track, artist, album, title, old in self.cursor:
            folder_name = os.path.join(self.path, valid_filename(artist),
                                       valid_filename(album))
            filename = os.path.join(folder_name,
                valid_filename('{track:0=2} {title}.mp3'.format(track=track,
                                                                title=title)))
            if old != filename:
                verify_dir(folder_name)
                moved.append((shutil.copy(old, filename), old))

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
        self.sql_connection.commit()

    def writeout(self):
        self.cursor.execute('select track, artist, album, title, filename, has_file from songs')
        for song in self.cursor:
            (track, artist, album, title, filename, has_file) = song
            if has_file:
                tag = open_tag(filename)
                tag._frames.clear()
                tag.track = track
                tag.artist = artist
                tag.album = album
                tag.title = title
                tag.write()

    def pretty_print(self, only_good=True):
        self.cursor.execute('select artist, title, filename from songs')
        for song in self.cursor:
            (artist, title, filename) = song
            print('{} -- {}'.format(artist, title))

    def print_tags(self):
        self.cursor.execute('select filename from songs')
        for i in self.cursor:
            print('\n'.join((map(repr, open_tag(i[0]).frames()))) + '\n')

    def user_control(self):
        self.cursor.execute('select distinct album from songs where conf_album=0 or conf_title=0')
        albums = self.cursor.fetchall()
        for (album,) in albums:
            print('Album: ', album)
            if get_yn_promt('Is that correct? '):
                self.cursor.execute('update songs set conf_album=1 where album=?', (album,))
            else:
                promt = attepmt_to_correct(album)
                if promt != album:
                    self.cursor.execute('update songs set conf_album=1, album=? '
                                        ' where album=?',
                                         (promt, album))
                else:
                    self.cursor.execute('update songs set conf_album=0 '
                                        ' where album=?', (album,))

            self.cursor.execute("select title from songs where album=? and conf_title=0",
                                (album,))
            songs = self.cursor.fetchall()

            if not songs:
                continue

            for (title,) in songs:
                print(title)

            if not get_yn_promt('Are they all correct? '):
                for (title,) in songs:
                    promt = attepmt_to_correct(title)
                    if promt != title:
                        self.cursor.execute('update songs set conf_title=1, title=? '
                                            ' where title=? and album=?',
                                             (promt, title, album))
                    else:
                        self.cursor.execute('update songs set conf_title=0 '
                                            ' where title=? and album=?',
                                             (title, album))
            else:
                self.cursor.execute('update songs set conf_title=1 where album=?', (album,))
        self.sql_connection.commit()

    @lru_cache()
    def search(self, request, what, incorrect=False):
        attepmts = [('utf-8', 'utf-8'), ('cp1252', 'cp1251')]
        result = None
        assert (what in {'artist', 'album', 'track'})
        for dst, src in attepmts[incorrect:]:
            suggest = request.encode(dst).decode(src)
            try:
                if suggest != request:
                    local = difflib.get_close_matches(suggest,
                                                      getattr(self, what + 's'),
                                                      1, 0.8)
                    if local:
                        result = local[0]
                        break
                search = getattr(self.network, 'search_for_' + what)(suggest)
                result = search.get_next_page()
                if result:
                    result = result[0].get_name(True)
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
        self.sql_connection.commit()

    def print_artists(self):
        self.cursor.execute('select * from artists')
        for name, confirmed in self.cursor:
            print(name, ['not', ''][confirmed], 'confirmed')


database = Database('/home/dani/yamp')
print('Started import')
database.import_folder('/home/dani/tmporig')
print('Imported tmporig')
database.import_folder('/home/dani/Music')
# database.pretty_print()
database.correct_artists()
database.print_artists()
database.correct_artists()
database.print_artists()
database.pretty_print()
database.move_files()
# database.user_control()
# database.correct_tags()
database.writeout()
