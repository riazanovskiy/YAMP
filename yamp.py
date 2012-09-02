# -*- coding: utf-8 -*-
print ('Started ' + __name__)
import sys
import os
import shutil
import sqlite3
from tags import open_tag


def filesize(file):
    return os.stat(file).st_size


def is_music_file(filename):
    return filename.endswith('.mp3') and filesize(filename)


def valid_filename(filename):
    invalid = frozenset('*”"/\[]:;|=,')
    return ''.join('-' if i in invalid else i for i in filename)


def printsong(S):
    s = repr(S)
    try:
        print(s)
        return
    except:
        pass
    try:
        s = s.encode('latin-1').decode('cp1251')
    except:
        try:
            s = s.encode('latin-2').decode('utf-8')
        except:
            try:
                print (S.filename)
            except:
                pass
    try:
        print(s)
    except:
        pass
    # print('Filename ', S.filename)
    sys.stdout.flush()


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
        # self.cursor.execute('pragma synchronous = NORMAL')
        # self.cursor.execute('pragma count_changes = OFF')
        self.cursor.execute('create table if not exists songs (track int,'
                            ' artist text, album text, title text, bitrate int,'
                            ' duration int, filename text, filehash blob,'
                            ' has_file boolean)')

    def import_folder(self, folder):
        self.cursor.execute('begin')
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
                print(filename)
                try:
                    filename = shutil.copy(file, filename)
                except shutil.Error:
                    pass
                self.cursor.execute('insert into songs (track, artist, album,'
                                    ' title, bitrate, duration, filename, has_file)'
                                    'values (?, ?, ?, ?, ?, ?, ?, 1)', (track,
                                    artist, album, title, bitrate, duration,
                                    filename))
        # self.cursor.execute('commit')
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
        # print('here')
        self.cursor.execute('select artist, title from songs')
        for song in self.cursor:
            (artist, title) = song
            print('{} -- {}'.format(artist, title))

    # def print_bad_songs(self):
    #     for song in sorted(self.data):
    #         if song.confirmed == False:
    #             printsong(song)

    # def wipe_tags(self):
    #     bad_tags = {'PRIV', 'MCDI', 'COMR', 'WCOM', 'WCOP', 'WOAF', 'WOAR',
    #                 'WOAS', 'WORS', 'WPAY', 'WPUB', 'WXXX', 'USER', 'OWNE',
    #                 'TENC', 'COMM', 'TPUB', 'TDEN', 'TDTG', 'TCOP'}

    #     for i in self.data:
    #         i.tags._frames = {key: val for key, val in i.tags._frames.items() if key not in bad_tags}

    # def print_tags(self):
    #     for i in self.data:
    #         print('\n'.join((map(repr, i.tags.frames()))) + '\n')

    def user_control(self, data=None, full=False):
        if not data:
            data = self.data
        print('Count: ', len(data))
        for album in get_by_albums(data):
            bad = False
            try:
                for song in album:
                    printsong(song)
            except:
                bad = True
            if not get_yn_promt('Are they all correct? ') or bad:
                if len(album) == 1:
                    album[0].confirmed == False
                else:
                    if get_yn_promt('Are they all incorrect? '):
                        for song in album:
                            song.confirmed = False
                    else:
                        for song in album:
                            printsong(song)
                            song.confirmed = get_yn_promt('Is it correct? ')
            else:
                for song in album:
                    song.confirmed = True

database = Database('/home/dani/yamp')
# database.import_folder('/home/dani/yamp_')
# database.wipe_tags()
database.pretty_print()
# database.writeout()
# database.print_tags()
# database.save()
