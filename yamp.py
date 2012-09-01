# -*- coding: utf-8 -*-
print ('Started ' + __name__)
import sys
import os
import chardet
import pickle
import shutil
import string
import sqlite3

from song import Song

encoings_map = {'windows-1251': 'cp1251',
                'MacCyrillic': 'mac_cyrillic',
                'ascii': 'ascii',
                None: None,
                'ISO-8859-8': 'iso8859_8',  # hebrew
                'ISO-8859-7': 'iso8859_7'  # greek
                }


def utf2cp1251(S):
    try:
        return S.encode('utf-8').decode('cp1251')
    except Exception:
        return S

enclist = ['ascii', 'big5', 'big5hkscs', 'cp037', 'cp424', 'cp437', 'cp500',
           'cp737', 'cp775', 'cp850', 'cp852', 'cp855', 'cp856', 'cp857', 'cp860',
           'cp861', 'cp862', 'cp863', 'cp864', 'cp865', 'cp866', 'cp869', 'cp874',
           'cp875', 'cp932', 'cp949', 'cp950', 'cp1006', 'cp1026', 'cp1140',
           'cp1250', 'cp1251', 'cp1252', 'cp1253', 'cp1254', 'cp1255', 'cp1256',
           'cp1257', 'cp1258', 'euc_jp', 'euc_jis_2004', 'euc_jisx0213', 'euc_kr',
           'gb2312', 'gbk', 'gb18030', 'hz', 'iso2022_jp', 'iso2022_jp_1',
           'iso2022_jp_2', 'iso2022_jp_2004', 'iso2022_jp_3', 'iso2022_jp_ext',
           'iso2022_kr', 'latin_1', 'iso8859_2', 'iso8859_3', 'iso8859_4',
           'iso8859_5', 'iso8859_6', 'iso8859_7', 'iso8859_8', 'iso8859_9',
           'iso8859_10', 'iso8859_13', 'iso8859_14', 'iso8859_15', 'johab',
           'koi8_r', 'koi8_u', 'mac_cyrillic', 'mac_greek', 'mac_iceland',
           'mac_latin2', 'mac_roman', 'mac_turkish', 'ptcp154', 'shift_jis',
           'shift_jis_2004', 'shift_jisx0213', 'utf_16', 'utf_16_be', 'utf_16_le',
           'utf_7', 'utf_8', 'utf_8_sig']


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


def get_by_albums(data):
    last = None
    albums = []
    for i in sorted(data):
        if i.tags.album != last:
            last = i.tags.album
            albums.append([i])
        else:
            albums[-1].append(i)
    return albums


def get_by_artists(data):
    last = None
    artists = []
    for i in sorted(data):
        if i.tags.artist != last:
            last = i.tags.artist
            artists.append([i])
        else:
            artists[-1].append(i)
    return artists


def verify_dir(name):
    # good = True
    # try:
    #     name.encode('utf-8').decode('ascii')
    # except:
    #     good = False
    # # print('Good', good)
    # try:
    #     print(name)
    # except:
    #     pass

    if not os.path.isdir(name):
        os.makedirs(name)


class Database:
    def __init__(self, path):
        self.data = set()
        self.path = path
        self.datapath = os.path.join(path, 'database')
        self.sql_connection = sqlite3.connect(self.datapath)
        self.cursor = self.sql_connection.cursor()
        self.cursor.execute('pragma synchronous = NORMAL')
        self.cursor.execute('pragma count_changes = OFF')
        self.cursor.execute('create table if not exists songs (track int,'
                            ' artist text, album text, title text, bitrate int,'
                            ' duration int, filename text, filehash blob,'
                            ' has_file boolean)')
# track, artist, album, title, bitrate, duration

    def import_folder(self, folder):
        what_to_add = set()
        for curr, dirs, files in os.walk(folder):
            for file in (os.path.join(curr, i) for i in files if is_music_file(os.path.join(curr, i))):
                with Song(file).tags as tags:
                    verify_dir(os.path.join(self.path, tags.artist.strip()))
                    verify_dir(os.path.join(self.path, artist_name, album_name))

                track, artist, album, title, bitrate, duration
                self.cursor.execute('insert into songs (track, artist, album,'
                                    ' title, bitrate, duration, filename, has_file)')
        # self.user_control(what_to_add)
        print(self.path)
        print(folder)
        for artist in get_by_artists(what_to_add):
            artist_name = artist[0].tags.artist.strip()
            verify_dir(os.path.join(self.path, artist_name))
            for album in get_by_albums(artist):
                album_name = album[0].tags.album.strip()
                verify_dir(os.path.join(self.path, artist_name, album_name))
                for song in album:
                    filename = valid_filename('{track:0=2} {title}.mp3'.format(track=song.tags.track,
                                                                               title=song.tags.title.strip()).strip())
                    song.filename = shutil.copy(song.filename,
                         os.path.join(self.path, artist_name, album_name,
                                      filename).strip())
        self.data.update(what_to_add)

    def writeout(self):
        for song in self.data:
            song.tags.write()

    def pretty_print(self, only_good=True):
        print('Count: ', len(self.data))
        for song in sorted(self.data):
            if song.confirmed or not only_good:
                printsong(song)

    def print_bad_songs(self):
        for song in sorted(self.data):
            if song.confirmed == False:
                printsong(song)

    def wipe_tags(self):
        bad_tags = {'PRIV', 'MCDI', 'COMR', 'WCOM', 'WCOP', 'WOAF', 'WOAR',
                    'WOAS', 'WORS', 'WPAY', 'WPUB', 'WXXX', 'USER', 'OWNE',
                    'TENC', 'COMM', 'TPUB', 'TDEN', 'TDTG', 'TCOP'}

        for i in self.data:
            i.tags._frames = {key: val for key, val in i.tags._frames.items() if key not in bad_tags}

    def print_tags(self):
        for i in self.data:
            print('\n'.join((map(repr, i.tags.frames()))) + '\n')

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

    def save(self):
        with open(self.datapath, 'wb') as file:
            pickle.dump(self.data, file)

    def utfy(self):
        for song in self.data:
            pass

database = Database('/home/dani/yamp')
# database.import_folder('/home/dani/testing')
# database.wipe_tags()
# database.writeout()
# database.print_tags()
# database.save()
