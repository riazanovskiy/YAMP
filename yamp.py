# -*- coding: utf-8 -*-
print ('Started ' + __name__)
import os
from log import logger
import shutil
import sqlite3
from tags import open_tag


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
        self.path = os.path.abspath(path)
        self.datapath = os.path.join(path, 'database')
        self.sql_connection = sqlite3.connect(self.datapath)
        self.cursor = self.sql_connection.cursor()
        self.cursor.execute('pragma synchronous = NORMAL')
        self.cursor.execute('pragma count_changes = OFF')
        self.cursor.execute('create table if not exists songs (track int,'
                            ' artist text, album text, title text, bitrate int,'
                            ' duration int, filename text,'
                            ' has_file boolean, confirmed boolean, '
                            ' unique(artist, title, album))')
        self.cursor.execute('create unique index if not exists songsindex '
                            'ON songs(artist, title, album, filename)')

    def import_folder(self, folder):
        for curr, dirs, files in os.walk(folder):
            for file in (os.path.join(curr, i) for i in files if is_music_file(os.path.join(curr, i))):
                tags = open_tag(file)

                track = tags.track
                artist = tags.artist.strip()
                album = tags.album.strip()
                title = tags.title.strip()
                # FIXME
                bitrate = 0
                duration = 0

                folder_name = os.path.join(self.path, valid_filename(artist),
                                           valid_filename(album))
                verify_dir(folder_name)
                filename = os.path.join(folder_name,
                    valid_filename('{track:0=2} {title}.mp3'.format(track=track,
                                                                    title=title)))
                # try:
                #     pass
                filename = shutil.copy(file, filename)
                # except shutil.Error:
                #     logger.error('Can not copy file')

                self.cursor.execute('insert or ignore into songs (track, artist, album,'
                                    ' title, bitrate, duration, filename, has_file, confirmed)'
                                    'values (?, ?, ?, ?, ?, ?, ?, 1, 0)', (track,
                                    artist, album, title, bitrate, duration,
                                    filename))
        self.sql_connection.commit()

# (track, artist, album, title, bitrate, duration, filename, filehash, has_file)
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
        self.cursor.execute('select artist, title from songs')
        for song in self.cursor:
            (artist, title) = song
            print('{} -- {}'.format(artist, title))

    def print_tags(self):
        self.cursor.execute('select filename from songs')
        for i in self.cursor:
            print('\n'.join((map(repr, open_tag(i[0]).frames()))) + '\n')

    def user_control(self, full=False):
        print('\n\n\n')
        self.cursor.execute('select distinct album from songs')
        albums = self.cursor.fetchall()
        for album in albums:
            self.cursor.execute("select artist, title from songs where album=? and confirmed<>1",
                                album)
            songs = self.cursor.fetchall()
            if not songs:
                continue
            print('Album: ', album[0])
            for artist, title in songs:
                print('{} -- {}'.format(artist, title))

            if not get_yn_promt('Are they all correct? '):
                if len(songs) == 1:
                    self.cursor.execute('update songs set confirmed=1 where title=? and artist=?',
                                         songs[0])
                else:
                    if get_yn_promt('Are they all incorrect? '):
                        self.cursor.execute('update songs set confirmed=0 where album=?', album)
                    else:
                        for artist, title in songs:
                            print('{} -- {}'.format(artist, title))
                            self.cursor.execute('update songs set confirmed=? where title=? and artist=?',
                                                (get_yn_promt('Is it correct? '), title, artist))
            else:
                self.cursor.execute('update songs set confirmed=1 where album=?', album)
        self.sql_connection.commit()

    def correct_tags(self):
        print('\n\n')
        self.cursor.execute('select artist, album, title from songs where confirmed=0')
        update_needed = self.cursor.fetchall()
        for artist, album, title in update_needed:
            print('{} -- {}'.format(artist, title))
            attepmts = [('cp1252', 'cp1251')]
            succeeded = 0
            for dst, src in attepmts:
                try:
                    print('{} -- {}'.format(artist.encode(dst).decode(src),
                                            title.encode(dst).decode(src)))
                    succeeded += 1
                except:
                    pass

            idx = 0
            if succeeded:
                promt = input('Which is correct? [0-%i] ' % succeeded)
                while(not promt.isdigit()) or not (0 < int(promt) <= succeeded):
                    promt = input('Which is correct? [0-%i] ' % succeeded)
                idx = int(promt)
            if 0 < idx <= succeeded:
                idx -= 1
                self.cursor.execute('update songs set artist=?, title=? where artist=? and title=?',
                                    (artist.encode(attepmts[idx][0]).decode(attepmts[idx][1]),
                                     title.encode(attepmts[idx][0]).decode(attepmts[idx][1]),
                                     artist, title))
            elif idx == 0:
                new_artist = input('Enter correct artist ') or artist
                new_title = input('Enter correct title ') or title
                self.cursor.execute('update songs set artist=?, title=? where artist=? and title=?',
                                    (new_artist, new_title, artist, title))

database = Database('/home/dani/yamp_')
database.import_folder('/home/dani/yamp')
# database.pretty_print()
database.user_control()
database.correct_tags()
database.writeout()
