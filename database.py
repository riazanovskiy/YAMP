# -*- coding: utf-8 -*-
import os
import shutil
import sqlite3
import re
import random
import string
from collections import defaultdict
from pprint import pprint

import mp3utils

import onlinedata
from log import logger
from onlinedata import OnlineData
from tags import open_tag
import misc
from misc import (filesize, is_all_ascii, levenshtein, normalcase,
                  improve_encoding, valid_filename, verify_dir)
from errors import NotFoundOnline


def is_music_file(filename):
    return filename.endswith('.mp3') and filesize(filename)


class Database:
    def __init__(self, path, use_grooveshark=True):
        self.online = OnlineData(use_grooveshark=use_grooveshark)
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
        self.songs_cache = {}

    def move_file(self, old_filename, track, artist, album, title):
        folder_name = os.path.join(self.path, valid_filename(artist), valid_filename(album))
        filename = os.path.join(folder_name,
                                valid_filename('{track:0=2} {title}.mp3'.format(track=track,
                                                                                title=title)))
        if old_filename != filename:
            verify_dir(folder_name)
            return (shutil.copy(old_filename, filename), old_filename)

    def move_files(self):
        cursor = self.sql.execute('select track, artist, album, title, filename from songs')
        moved_list = []
        for track, artist, album, title, old_filename in cursor:
            if not old_filename.startswith('NOFILE') and os.path.exists(old_filename):
                moved = self.move_file(old_filename, track, artist, album, title)
                if moved:
                        moved_list.append(moved)

        print(len(moved_list), 'files moved.')
        if moved_list:
            self.sql.executemany('update songs set filename=? where filename=?',
                                 moved_list)
            self.sql.commit()

    def import_file(self, file):
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
                         'values (?, ?, ?, ?, ?, ?, ?, 1)',
                         (track, artist, album, title, bitrate, duration, file))

    def import_folder(self, folder):
        count = self.sql.execute('select count (*) from songs').fetchone()[0]
        for curr, dirs, files in os.walk(folder):
            for file in (os.path.join(curr, i) for i in files if is_music_file(os.path.join(curr, i))):
                self.import_file(file)
        print(self.sql.execute('select count (*) from songs').fetchone()[0] - count,
              'songs imported')
        self.sql.commit()

    def writeout(self):
        cursor = self.sql.execute('select track, artist, album, title, filename '
                                  ' from songs where has_file=1')
        for track, artist, album, title, filename in cursor:
            tag = open_tag(filename)
            tag._frames.clear()
            tag.track, tag.artist, tag.album, tag.title = track, artist, album, title
            tag.write()

    def pretty_print(self, artist=None, album=None):
        if artist:
            print(artist)
            cursor = self.sql.execute('select distinct album from songs where artist=?', (artist,))
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

    def transliterate_album(self, album):
        data = self.sql.execute('select title, artist from songs where album=?',
                                (album,)).fetchall()
        artist = data[0][1]
        data = {title: title for title, artist in data}
        new_album = album
        if misc.measure_spelling(album) < 0.3:
            new_album = self.transliterate('album', album, artist)
            print('REPLACING', album, 'WITH', new_album)

        for old in data:
            data[old] = self.transliterate('track', old, artist)

        for old, new in data.items():
            if old != new:
                print('REPLACING', old, 'WITH', new)
                self.sql.execute('update or ignore songs set title=?, album=? where title=?',
                                 (new, new_album, old))
                self.sql.execute('delete from songs where title=?', (old,))
        self.sql.commit()

    def transliterate(self, what, orig, artist):
        request = misc.get_translit(orig)
        try:
            return self.online.generic(what, request, artist=artist).name
        except NotFoundOnline:
            words = re.sub('[][._/(:;\)-]', ' ', request).split()
            good_words = []
            dictionary = misc.dictionaries[-1]

            for i, word in enumerate(words):
                if dictionary.check(word):
                    good_words.append(word)
                elif dictionary.suggest(word):
                    words[i] = dictionary.suggest(word)[0]

            suggest1 = ' '.join(words)
            suggest2 = ' '.join(good_words)
            try:
                return self.online.generic(what, suggest1, artist=artist).name
            except NotFoundOnline:
                if suggest2:
                    try:
                        return self.online.generic(what, suggest2, artist=artist).name
                    except NotFoundOnline:
                        return request
                else:
                    return request

    def generic_correction(self, what):
        assert (what in ['album', 'artist', 'track'])
        field = what if what != 'track' else 'title'
        cursor = self.sql.execute('select distinct {} from songs where {}_as_online=0'.format(field, field))
        data = {i: i for i, in cursor}

        for i in data:
            data[i] = improve_encoding(i)

        case_mapping = defaultdict(list)
        for i in data.values():
            case_mapping[normalcase(i)].append(i)

        corrected_case = {}
        for i in case_mapping:
            if (len(case_mapping[i]) > 1 or case_mapping[i][0].isupper()
                or case_mapping[i][0].islower()):
                artist = ''
                if field != 'artist':
                    artist = self.sql.execute('select artist from songs where {}=?'.format(field),
                                              (case_mapping[i][0],)).fetchone()
                    if artist:
                        artist = artist[0]
                try:
                    corrected_case[i] = self.online.generic(what, i, artist=artist).name
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
        self.sql.commit()

    def correct_artist(self, artist):
        logger.debug('in correct_artist(%s)' % artist)
        already = self.sql.execute('select artist_as_online from songs where artist=?',
                                   (artist,)).fetchone()
        if already and already[0]:
            return artist
        improved = self.online.generic('artist', artist).name
        artists = self.sql.execute('select distinct artist from songs').fetchall()
        artists = {i: normalcase(i) for i, in artists if i}
        query = normalcase(artist)
        for i, j in artists.items():
            if i != improved and j == query:
                print('REPLACING', i, 'WITH', improved)
                self.sql.execute('update or ignore songs set artist=?, artist_as_online=1 where artist=?',
                                 (improved, i))
                self.sql.execute('delete from songs where artist=?', (i,))
        self.sql.commit()
        return improved

    def correct_album(self, album):
        improved = self.online.generic('album', album)
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
        self.sql.commit()
        return improved

    def fetch_tracks_for_artist(self, artist, count=15):
        inserted = self.sql.execute('select count (*) from songs').fetchone()[0]
        count = min(count, 100)
        try:
            artist = self.correct_artist(artist)
        except NotFoundOnline:
            print('0 songs added')
            return
        cursor = self.sql.execute('select title from songs where artist=?', (artist,))
        known_tracks = {i for i, in cursor}

        suggestions = []
        fetched_artist = self.online.artist(onlinedata.LASTFM, artist)
        suggestions += fetched_artist.tracks() if fetched_artist else []
        fetched_artist = self.online.artist(onlinedata.GROOVESHARK, artist)
        suggestions += fetched_artist.tracks() if fetched_artist else []
        suggestions = [i for i in suggestions if i.name not in known_tracks]
        suggestions = [i for i in suggestions if not any(j in i.name for j in known_tracks) and i.album]

        for song in suggestions[:count]:
            self.sql.execute('insert or ignore into songs'
                             ' (artist, title, album, track, filename, has_file)'
                             ' values (?, ?, ?, ?, ?, 0)',
                             (artist, song.name, song.album, song.track, 'NOFILE' +
                             ''.join(random.choice(string.hexdigits) for x in range(16))))
        self.sql.commit()
        print(self.sql.execute('select count (*) from songs').fetchone()[0] - inserted,
              'songs added')

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
            improved = self.online.generic('artist', artist)
            print('REPLACING', artist, 'WITH', improved)
            for i, j in artists.items():
                if j == artist:
                    self.sql.execute('update or ignore songs set artist=? where artist=?',
                                        (improved, i))
                    self.sql.execute('delete from songs where artist=?', (i,))
        self.sql.commit()

    def fill_album(self, artist, albumname):
        logger.debug('fill_album(' + str(artist) + ', ' + str(albumname) + ')')
        min_tracks = 0
        tracknames = []
        known_tracks = []
        if artist:
            try:
                artist = self.correct_artist(artist)
            except NotFoundOnline:
                return
            known_tracks = self.sql.execute('select track, title from songs where artist=? and album=?',
                                            (artist, albumname)).fetchall()
            known_tracks = [(track, title, normalcase(title)) for track, title in known_tracks]
            if known_tracks:
                known_tracks.sort()
                min_tracks = known_tracks[-1][0]
                tracknames = [i[2] for i in known_tracks]
        album = (self.online.album(onlinedata.BRAINZ, albumname, artist,
                                   tracknames, min_tracks)
                 or self.online.album(onlinedata.LASTFM, albumname, artist,
                                      tracknames, min_tracks)
                 or self.online.album(onlinedata.GROOVESHARK, albumname, artist,
                                      tracknames, min_tracks))

        if not album:
            try:
                albumname = self.correct_album(albumname)
            except NotFoundOnline:
                print(albumname, 'not found online')
                return
            album = (self.online.album(onlinedata.BRAINZ, albumname, artist)
                     or self.online.album(onlinedata.LASTFM, albumname, artist)
                     or self.online.album(onlinedata.GROOVESHARK, albumname, artist))
        assert(album)
        if not artist:
            artist = album.artist
        for i, track in enumerate(album.tracks()):
            for idx, song, norm in known_tracks:
                if norm == normalcase(track.name):
                    if i + 1 != idx or song != track.name:
                        if i + 1 != idx:
                            print('Song', song, ': ', idx, ' -> ', i + 1)
                        if song != track.name:
                            print('REPLACING', song, 'WITH', track.name)
                        try:
                            self.sql.execute('update songs set track=?, title=?, '
                                                ' artist_as_online=1, album_as_online=1, title_as_online=1 '
                                                ' where title=? and artist=? and album=?',
                                                (i + 1, track.name,
                                                 song, artist, albumname))
                        except sqlite3.IntegrityError:
                            self.sql.execute('delete from songs where track=? and '
                                             ' title=? and artist=? and album=?',
                                             (idx, song, artist, albumname))
                    break
            else:
                try:
                    self.sql.execute('insert into songs (track, artist, album, '
                                     ' title, filename, has_file) '
                                     'values (?, ?, ?, ?, ?, 0) ',
                                     (i + 1, artist, albumname, track.name,
                                      'NOFILE' + ''.join(random.choice(string.hexdigits) for x in range(16))))
                except sqlite3.IntegrityError:
                    print('Can not insert: artist ', artist, 'album ', albumname, 'track', fetched_tracks[i][0])
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
        if artist:
            return artist[0]
        else:
            return ''

    def reduce_album(self, artist, album):
        self.fill_album(artist, album)
        tracks = self.sql.execute('select track, title from songs where artist=? and album=?',
                                  (artist, album)).fetchall()
        tracks.sort()
        same = defaultdict(list)
        for track, title in tracks:
            same[track].append(title)

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
        self.sql.commit()

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
        self.sql.commit()

    def track_numbers(self):
        self.track_numbers_from_filename()
        self.track_numbers_from_title()

    def fetch_data(self, count=0):
        songs = list(self.sql.execute("select title, artist, album, track, filename "
                                 " from songs where filename like 'NOFILE%'"))
        if count > 0:
            songs = songs[:count]
        data = [song[:-1] for song in songs]
        if len(data):
            print('Fetching', len(data), 'song' + ('s' if len(data) > 1 else ''))
        else:
            print('No songs to fetch')
            return
        new_files = self.online.download_by_list(data)
        if len(new_files) != len(songs):
            return
        success = 0
        for (title, artist, album, track, dummy_filename), new_filename in zip(songs, new_files):
            if not new_filename:
                logger.debug('download of ' + title + ' failed, omitting')
                continue
            right_filename = self.move_file(new_filename, track, artist, album, title)[0]
            self.sql.execute('update songs set filename=? where filename=?',
                             (right_filename, dummy_filename))
            os.remove(new_filename)
            success += 1
        self.sql.commit()
        print(success, 'songs successfully downloaded')


if __name__ == '__main__':
    random.seed()
    # database = Database('/home/dani/yamp')
    # database.import_folder('/home/dani/Music')

    # database.import_folder('/home/dani/tmp')
    # database.import_folder('/home/dani/tmp_')
    # database.import_folder('/home/dani/Fleur')
    database.remove_extensions_from_tracks()
    print('\x1b[41mTrack numbers\x1b[0m')
    database.track_numbers()
    print('\x1b[41mArtist correction\x1b[0m')
    database.generic_correction('artist')
    print('\x1b[41mAlbum correction\x1b[0m')
    database.generic_correction('album')
    print('\x1b[41mTrack correction\x1b[0m')
    database.generic_correction('track')

##########################################

    # database.pretty_print()
    # database.fill_album('Несчастный случай', 'Тоннель в конце света')
    # database.fill_album('Наутилус Помпилиус', 'Князь тишины (VinylRip)')
    # database.fill_album('Pink Floyd', 'The Dark Side of the Moon')
    # database.fetch_tracks_for_artist('Pink Floyd', count=30)
    # database.fetch_tracks_for_artist('Сплин')
    # database.reduce_albums()
    database.pretty_print()
