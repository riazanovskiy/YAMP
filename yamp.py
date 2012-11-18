# -*- coding: utf-8 -*-
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
import colorama

import onlinedata
from log import logger
from onlinedata import OnlineData
from tags import open_tag
from misc import filesize, is_all_ascii, levenshtein, normalcase, improve_encoding
from errors import DoublecheckEncodingException, NotFoundOnline


def is_music_file(filename):
    return filename.endswith('.mp3') and filesize(filename)


class Database:
    def __init__(self, path):
        self.online = OnlineData()
        self.path = os.path.abspath(path)
        self.datapath = os.path.join(path, 'database')
        self.sql = sqlite3.connect(self.datapath)
        self.sql.execute('create table if not exists songs (track int,'
                         ' artist text, album text, title text, bitrate int,'
                         ' duration int, filename text unique,'
                         ' has_file boolean, '
                         # ' mbid text, '
                         ' artist_as_online boolean default 0, '
                         ' album_as_online boolean default 0, '
                         ' title_as_online boolean default 0,'
                         ' grooveshark_id int default 0, '
                         ' unique(artist, title, album))')

        self.sql.execute('create unique index if not exists songsindex '
                         'ON songs(artist, title, album, filename)')

    def move_files(self):
        cursor = self.sql.execute('select track, artist, album, title, filename from songs')
        moved = []
        for track, artist, album, title, old_filename in cursor:
            if not old_filename.startswith('NOFILE') and os.path.exists(old_filename):
                folder_name = os.path.join(self.path, valid_filename(artist),
                                           valid_filename(album))
                filename = os.path.join(folder_name, valid_filename('{track:0=2} {title}.mp3'.format(track=track,
                                                                                                     title=title)))
                if old_filename != filename:
                    verify_dir(folder_name)
                    moved.append((shutil.copy(old_filename, filename), old_filename))

        print(len(moved), 'files moved.')
        self.sql.executemany('update songs set filename=? where filename=?',
                                moved)
        self.sql.commit()

    def import_folder(self, folder):
        count = self.sql.execute('select count (*) from songs').fetchone()[0]
        for curr, dirs, files in os.walk(folder):
            for file in (os.path.join(curr, i) for i in files if is_music_file(os.path.join(curr, i))):
                tags = open_tag(file)

                track, artist = tags.track, tags.artist.strip()
                album, title = tags.album.strip(), tags.title.strip()
                # FIXME
                duration = 0
                try:
                    bitrate = mp3utils.mp3info(file)['BITRATE']
                except:
                    bitrate = 0

                self.sql.execute('insert or ignore into songs (track, artist, album,'
                                    ' title, bitrate, duration, filename, has_file)'
                                    'values (?, ?, ?, ?, ?, ?, ?, 1)', (track,
                                    artist, album, title, bitrate, duration,
                                    file))
        print(self.sql.execute('select count (*) from songs').fetchone()[0] - count,
              'songs imported')
        self.sql.commit()

    def writeout(self):
        cursor = self.sql.execute('select track, artist, album, title, filename, '
                                  ' from songs where has_file=1')
        for track, artist, album, title, filename in cursor:
            tag = open_tag(filename)
            tag._frames.clear()
            tag.track, tag.artist, tag.album, tag.title = track, artist, album, title
            tag.write()

    def pretty_print(self, artist=None, album=None):
        if artist:
            print(artist)
            cursor = self.sql.execute('select distinct album from songs where artist=?',
                                      (artist,))
            for i, in cursor:
                print('\t', i)
        elif album:
            print(album, 'by', self.get_artist_of_album(album))
            cursor = self.sql.execute('select track, title from songs where album=?', (album,))
            for track, title in sorted(cursor):
                print('#' + str(track), title)
        else:
            cursor = self.sql.execute('select artist, album, track, title from songs')
            for artist, album, track, title in sorted(cursor):
                print('{} -- {} -- #{} {}'.format(artist, album, track, title))

    def print_tags(self):
        cursor = self.sql.execute('select filename from songs where has_file=1')
        for i, in cursor:
            print('\n'.join((map(repr, open_tag(i).frames()))) + '\n')

    def generic_correction(self, what):
        assert (what in ['album', 'artist', 'track'])
        field = what if what != 'track' else 'title'
        cursor = self.sql.execute('select distinct {} from songs where {}_as_online=0'.format(field, field))
        data = {i: i for i, in cursor}

        for i in data:
            data[i] = improve_encoding(i)

        case_mapping = defaultdict(lambda: [])
        for i in data.values():
            case_mapping[normalcase(i)].append(i)

        corrected_case = {}
        for i in case_mapping:
            if (len(case_mapping[i]) > 1 or case_mapping[i][0].isupper()
                or case_mapping[i][0].islower()):
                artist = ''
                if field == 'title' or field == 'album':
                    artist = self.sql.execute('select artist from songs where {}=?'.format(field),
                                              (case_mapping[i][0],)).fetchone()
                    if artist:
                        artist = artist[0]
                try:
                    corrected_case[i] = self.online.generic_search(what, i, artist=artist)
                except NotFoundOnline:
                    corrected_case[i] = case_mapping[i][0]
            else:
                corrected_case[i] = case_mapping[i][0]

        for old, new in data.items():
            data[old] = corrected_case[normalcase(new)]

        for old, new in data.items():
            if old != new:
                print('REPLACING', old, 'WITH', new)
                self.sql.execute('update or ignore songs set {}=? where {}=?'.format(field, field),
                                    (new, old))
                self.sql.execute('delete from songs where {}=?'.format(field), (old,))
        self.sql.execute('update songs set {}_as_online=1'.format(field))
        self.sql.commit()

    def remove_extensions_from_tracks(self):
        cursor = self.sql.execute('select distinct title from songs')
        data = {i: i for i, in cursor}
        to_remove = ['.mp3', '.MP3', 'mp3', 'MP3']
        for i in data:
            for j in to_remove:
                if j in i:
                    data[i] = data[i].replace(j, '')
                    break
        for i, j in data.items():
            if i != j:
                print('REPLACING', i, 'WITH', j)
                self.sql.execute('update songs set title=? where title=?',
                                    (j, i))
        self.sql.commit()

    def remove_by_list(self, tracks, what):
        for i in tracks:
            updated = i.replace(what, '')
            if updated != i:
                print('REPLACING', i, 'WITH', updated)
                self.sql.execute('update songs set title=? where title=?',
                                    (updated, i))

    def correct_artist(self, artist):
        improved = self.online.generic_search('artist', artist)
        artists = self.sql.execute('select distinct artist from songs').fetchall()
        artists = {i: normalcase(i) for i, in artists if i}
        query = normalcase(artist)
        for i, j in artists.items():
            if i != improved and j == query:
                print('REPLACING', i, 'WITH', improved)
                self.sql.execute('update or ignore songs set artist=? where artist=?',
                                    (improved, i))
                self.sql.execute('delete from songs where artist=?', (i,))
        return improved

    def correct_album(self, album):
        improved = self.online.generic_search('album', album)
        if improved != album:
            print('REPLACING', album, 'WITH', improved)
            albums = self.sql.execute('select distinct album from songs').fetchall()
            albums = {i: normalcase(i) for i, in albums if i}
            query = normalcase(album)
            for i, j in albums.items():
                if j == query:
                    self.sql.execute('update or ignore songs set album=? where album=?',
                                        (improved, i))
                    self.sql.execute('delete from songs where album=?', (i,))
        return improved

    def fetch_tracks_for_artist(self, artist, count=20):
        count = min(count, 100)
        artist = self.correct_artist(artist)
        cursor = self.sql.execute('select title from songs where artist=?', (artist,))
        known_tracks = {i for i, in cursor}
        suggestions = self.online.get_tracks_for_artist(artist)
        # pprint(suggestions)
        suggestions = [i for i in suggestions if i[0] not in known_tracks]
        # pprint(suggestions)
        suggestions = [i for i in suggestions if not any(j in i[0] for j in known_tracks)]
        pprint(suggestions)

        for song in suggestions[:count]:
            self.sql.execute('insert or ignore into songs'
                                ' (artist, title, album, track, filename, has_file)'
                                ' values (?, ?, ?, ?, ?, 0)',
                                (artist, song[0], song[1], song[2], 'NOFILE' +
                                ''.join(random.choice(string.hexdigits) for x in range(16))))
        self.sql.commit()

    def merge_artists(self):
        artists = self.sql.execute('select distinct artist from songs').fetchall()
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
                    self.sql.execute('update or ignore songs set artist=? where artist=?',
                                        (improved, i))
                    self.sql.execute('delete from songs where artist=?', (i,))
        self.sql.commit()

    def fill_album(self, artist, album):
        print(artist, album)
        artist = self.correct_artist(artist)
        print(artist, album)

        known_tracks = self.sql.execute('select track, title from songs where artist=? and album=?',
                                        (artist, album)).fetchall()
        if known_tracks:
            known_tracks.sort()
            known_tracks_normalized = [normalcase(i) for j, i in known_tracks]
            known_tracks = [(known_tracks[i][0], known_tracks[i][1], known_tracks_normalized[i]) for i in range(len(known_tracks))]
            fetched_tracks = self.online.get_track_list(artist, album,
                                                        known_tracks[-1][0],
                                                        known_tracks_normalized)

        if not known_tracks or not fetched_tracks:
            try:
                album = self.correct_album(album)
            except NotFoundOnline:
                print(album, 'not found online')
                return
            fetched_tracks = self.online.get_track_list(artist, album)

        for i in range(len(fetched_tracks)):
            if len(fetched_tracks[i]) < 2:
                fetched_tracks[i] = (fetched_tracks[i][0], 0)
        # pprint(fetched_tracks)
        for i in range(len(fetched_tracks)):
            # print(song)
            for idx, song, norm in known_tracks:
                if norm == normalcase(fetched_tracks[i][0]):
                    if i + 1 != idx or song != fetched_tracks[i][0]:
                        if i + 1 != idx:
                            print('Song', song, ': ', idx, ' -> ', i + 1)
                        if song != fetched_tracks[i][0]:
                            print('REPLACING', song, 'WITH', fetched_tracks[i][0])
                        self.sql.execute('update songs set track=?,  grooveshark_id=?, title=?, '
                                            ' artist_as_online=1, album_as_online=1, title_as_online=1 '
                                            ' where title=? and artist=? and album=?',
                                            (i + 1, fetched_tracks[i][1], fetched_tracks[i][0],
                                             song, artist, album))
                    break
            else:
                try:
                    self.sql.execute('insert into songs (grooveshark_id, track, artist, album, '
                                                          ' title, filename, has_file) '
                                        'values (?, ?, ?, ?, ?, ?, 0) ',
                                        (fetched_tracks[i][1], i + 1, artist, album, fetched_tracks[i][0],
                                         'NOFILE' + ''.join(random.choice(string.hexdigits) for x in range(16))))
                except sqlite3.IntegrityError:
                    print('Can not insert: artist ', artist, 'album ', album, 'track', fetched_tracks[i][0])
        self.sql.commit()

    def get_artists_list(self):
        cursor = self.sql.execute('select distinct artist from songs')
        return (i for i, in cursor if i)

    def get_albums_list(self, artist=None):
        if artist:
            cursor = self.sql.execute('select distinct album from songs where artist=?',
                                (artist,))
        else:
            cursor = self.sql.execute('select distinct album from songs')
        return (i for i, in cursor if i)

    def get_artist_of_album(self, album):
        artist = self.sql.execute('select artist from songs where album=?', (album,)).fetchone()
        if artists:
            return artists[0]
        else:
            return self.online.artist_of_album(album)

    def reduce_album(self, artist, album):
        # print('Processing', album, 'by', artist)
        self.fill_album(artist, album)
        tracks = self.sql.execute('select track, title from songs where artist=? and album=?',
                                  (artist, album)).fetchall()
        tracks.sort()
        same = defaultdict(lambda: [])
        for track, title in tracks:
            same[track].append(title)
        # for i, j in same.items():
        #     if len(j) > 1:
        #         print(j)

    def reduce_albums(self):
        artists = self.sql.execute('select distinct artist from songs').fetchall()
        for artist, in artists:
            albums = self.sql.execute('select distinct album from songs where artist=?',
                                      (artist,)).fetchall()
            for album, in albums:
                tracks = self.sql.execute('select track, title from songs where artist=? and album=?',
                                          (artist, album)).fetchall()
                tracks.sort()
                if len(tracks) > 1:
                    for i in range(len(tracks) - 1):
                        if tracks[i][0] == tracks[i + 1][0]:
                            self.reduce_album(artist, album)
                            break

    def track_numbers_from_title(self):
        artists = self.sql.execute('select distinct artist from songs').fetchall()
        for artist, in artists:
            albums = self.sql.execute('select distinct album from songs where artist=?',
                                      (artist,)).fetchall()
            for album, in albums:
                tracks = self.sql.execute('select track, title from songs where artist=? and album=? and title_as_online=0',
                                          (artist, album)).fetchall()
                tracks = sorted(tracks)
                for track, title in tracks:
                    if len(title) < 3:
                        continue
                    if title[:2].isdigit():
                        old_title = title
                        title = title.strip()
                        num = int(title[:2])
                        if track == num or track == 0:
                            title = title[2:]
                            title = title.strip()
                            if title[0] == '.':
                                title = title[1:]
                            elif title[0] == '-':
                                title = title[1:]
                            title = title.strip()
                            print('REPLACING #' + str(track), old_title,
                                  'WITH #' + str(num), title)
                            self.sql.execute('update or ignore songs set title=?, track=? '
                                                'where artist=? and album=? and title=?',
                                                (title, num, artist, album, old_title))
                            self.sql.execute('delete from songs where artist=? and album=? and title=?',
                                                (artist, album, old_title))

    def track_numbers_from_filename(self):
        cursor = self.sql.execute('select filename from songs where track=0')
        updated = dict()
        for filename, in cursor:
            if filename.strip()[:2].isdigit():
                track = int(filename.strip()[:2])
                updated[filename] = track
        for filename, track in updated.items():
            print('Song', filename, ':  0 ->', track)
            self.sql.execute('update songs set track=? where filename=?',
                                (track, filename))

    def track_numbers(self):
        self.track_numbers_from_filename()
        self.track_numbers_from_title()

if __name__ == '__main__':
    random.seed()
    database = Database('/home/dani/yamp')
    # database.import_folder('/home/dani/Music')

    # database.import_folder('/home/dani/tmp')
    # database.import_folder('/home/dani/tmp_')
    # database.remove_extensions_from_tracks()
    # print('\x1b[41mTrack numbers\x1b[0m')
    # database.track_numbers()
    # print('\x1b[41mArtist correction\x1b[0m')
    # database.generic_correction('artist')
    # print('\x1b[41mAlbum correction\x1b[0m')
    # database.generic_correction('album')
    # print('\x1b[41mTrack correction\x1b[0m')
    # database.generic_correction('track')

##########################################

    # database.pretty_print()
    # database.fill_album('Несчастный случай', 'Тоннель в конце света')
    database.correct_album('Князь тишины (VinylRip)')
    # database.fill_album('Наутилус Помпилиус', 'Князь тишины (VinylRip)')
    # database.fill_album('Pink Floyd', 'The Dark Side of the Moon')
    # database.fetch_tracks_for_artist('Pink Floyd', count=30)
    # database.fetch_tracks_for_artist('Сплин')
    # database.reduce_albums()
    database.pretty_print()
