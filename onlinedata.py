import random
import multiprocessing
import urllib
from pprint import pprint
from functools import lru_cache

import pylast
import grooveshark
import musicbrainzngs as brainz

import vpleer
from misc import diff, strip_brackets, improve_encoding, normalcase, strip_unprintable
from errors import NotFoundOnline
from tags import open_tag
from log import logger

LASTFM = 0
GROOVESHARK = 1
BRAINZ = 2


class LastSong:
    def __init__(self, song):
        self.artist = song.artist.name
        self.name = improve_encoding(song.title)
        album = song.get_album()
        self.album = None
        if album:
            self.album = improve_encoding(album.title)
        self.track = 0
        logger.debug('in LastSong(name=' + str(self.name) + ', album=' + str(self.album) + ')')


class LastAlbum:
    def __init__(self, album):
        self._link = album
        self.name = album.get_title()
        self.artist = album.get_artist().get_name()
        self._tracks = None

    def tracks(self):
        self._tracks = self._tracks or [LastSong(i) for i in self._link.get_tracks()]
        return self._tracks


class LastArtist:
    def __init__(self, artist):
        self._link = artist
        self.name = artist.get_name(properly_capitalized=True)
        self._tracks = None

    def tracks(self):
        logger.debug('in LastArtist.tracks()')
        self._tracks = self._tracks or [LastSong(i.item) for i in self._link.get_top_tracks()]
        return self._tracks


class SharkSong:
    def __init__(self, song):
        self.artist = song['ArtistName']
        if 'SongName' in song:
            self.name = improve_encoding(song['SongName'])
        else:
            self.name = improve_encoding(song['Name'])
        self.album = improve_encoding(song['AlbumName'])
        self.id = song['SongID']
        self.track = int(song['TrackNum'] or '0')

    def __lt__(self, other):
        return self.track < other.track


class SharkAlbum:
    def __init__(self, album):
        self.name = album['AlbumName']
        self.artist = album['ArtistName']
        self.id = album['AlbumID']
        self._tracks = None

    def tracks(self):
        if not self._tracks:
            tracks = sorted([SharkSong(i) for i in grooveshark.singleton.albumGetAllSongs(self.id)])
            i = 1
            self._tracks = [tracks[0]]
            while i < len(tracks):
                if self._tracks[-1].track != tracks[i].track:
                    self._tracks.append(tracks[i])
                i += 1

        return self._tracks


class SharkArtist:
    def __init__(self, artist):
        self.id = artist['ArtistID']
        self.name = artist['Name']
        self._tracks = None

    def tracks(self):
        self._tracks = self._tracks or [SharkSong(i) for i in grooveshark.singleton.artistGetAllSongsEx(self.id)]
        return self._tracks


class BrainzSong:
    def __init__(self, song):
        self.artist = song['artist-credit-phrase'] if 'artist-credit-phrase' in song else None
        self.name = song['title'] if 'title' in song else None
        self.id = song['id'] if 'id' in song else None
        self.track = song['position'] if 'position' is song else 0
        if 'recording' in song:
            if 'title' in song['recording']:
                self.name = song['recording']['title']
            if 'id' in song['recording']:
                self.id = song['recording']['id']

    def __lt__(self, other):
        return self.track < other.track


class BrainzAlbum:
    def __init__(self, album):
        self.name = album['title']
        self.artist = album['artist-credit-phrase']
        self.id = album['id']
        self._tracks = None

    def tracks(self):
        if not self._tracks:
            data = brainz.get_release_by_id(self.id, includes='recordings')['release']
            assert(self.name == data['title'])
            tracks = []
            for i in data['medium-list']:
                tracks += i['track-list']
            self._tracks = [BrainzSong(i) for i in tracks]
            for track in self._tracks:
                track.artist = self.artist
                track.album = self.name
        return self._tracks


class BrainzArtist:
    def __init__(self, artist):
        self.id = artist['id']
        self.name = artist['name']
        self._tracks = None

    def tracks(self):
        logger.critical('NotImplementedError')
        return []


class OnlineData:
    def __init__(self, use_grooveshark=True):
        self.lastfm = pylast.LastFMNetwork('e494d3c2d1e99307336886c9e1f18af2',
                                           '989f1acfe251e590981d485ad9a82bd1')
        if use_grooveshark:
            grooveshark.setup_connection()
            self.shark = grooveshark.singleton
        else:
            global GROOVESHARK
            GROOVESHARK = BRAINZ
        brainz.set_useragent('Kaganov"s Player', '1.00', 'http://lleo.me')

    @lru_cache()
    def _search_artist(self, provider, known):
        logger.info('In _search_artist(' + str(provider) + ', ' + known + ') ')
        RESULTS_TO_REVIEW = 3
        search = [lambda: self.lastfm.search_for_artist(known).get_next_page(),
                  lambda: self.shark.getResultsFromSearch(known, 'Artists')['result'],
                  lambda: brainz.search_artists(known)['artist-list']][provider]
        Artist = [LastArtist, SharkArtist, BrainzArtist][provider]
        output = None
        try:
            output = search()
        except Exception as exc:
            logger.critical('Exception in search')
            logger.exception(exc)
            return None
        if output:
            logger.info('got output')
            for i, result in enumerate(output):
                if i == RESULTS_TO_REVIEW:
                    break
                artist = Artist(result)
                logger.info('Got artist result ' + str(artist.name))
                if (diff(artist.name, known) < 0.5 or (provider == BRAINZ
                                                       and 'alias-list' in result
                                                       and known in result['alias-list'])):
                    return artist
                else:
                    logger.info(artist.name + ' differs from ' + known)
        else:
            logger.info('no output')
        return None

    @lru_cache()
    def artist(self, provider, known):
        return (self._search_artist(provider, known)
                or self._search_artist(provider, strip_brackets(known)))

    def _search_album(self, provider, title, artist='', tracks=[], min_tracks=0):
        logger.info('In _search_album(' + str(provider) + ', ' + str(title) + ', ' + str(artist) + ')')
        RESULTS_TO_REVIEW = 5 if artist else 40

        def searchlast():
            if artist:
                return [i.item for i in self.artist(LASTFM, artist)._link.get_top_albums()]
            else:
                search_results = self.lastfm.search_for_album(title)
                return search_results.get_next_page() + search_results.get_next_page()
        search = [lambda: searchlast(),
                  lambda: self.shark.getResultsFromSearch(title, 'Albums')['result'],
                  lambda: brainz.search_releases(title, artist=artist)['release-list']][provider]
        Album = [LastAlbum, SharkAlbum, BrainzAlbum][provider]
        output = None
        try:
            output = search()
        except Exception as exc:
            logger.critical('Exception in search')
            logger.exception(exc)
            return None
        if output:
            for i, result in zip(range(RESULTS_TO_REVIEW), output):
                logger.info('Album: attempt #' + str(i + 1))
                album = Album(result)
                if artist and diff(album.artist, artist) > 0.5:
                    logger.info('Omitting because ' + str(album.artist) + ' != ' + str(artist))
                    continue
                if diff(album.name, title) > 0.5:
                    logger.info('Omitting because of title: ' + str(album.name))
                    continue
                if min_tracks and len(album.tracks()) < min_tracks:
                    logger.info('Omitting because of min_tracks: only ' + str(len(album.tracks())))
                    continue
                if tracks:
                    album_tracks = [normalcase(i.name) for i in album.tracks()]
                    if any(known not in album_tracks for known in tracks):
                        logger.info('Omitting because track not found')
                        if False:
                            logger.debug('fetched ' + repr(album_tracks) + '\n\n known ' + repr(tracks))
                            for known in tracks:
                                if known not in album_tracks:
                                    logger.debug(known + ' not found in fetched')
                        continue
                return album

        return None

    def album(self, provider, title, artist='', tracks=[], min_tracks=0):
        if (artist and ('[' in artist or '(' in artist or ']' in artist or ')' in artist or
           '[' in title or '(' in title or ']' in title or ')' in title)):
            return (self._search_album(provider, title, artist, tracks, min_tracks)
                    or self._search_album(provider, strip_brackets(title),
                                          strip_brackets(artist),
                                          tracks, min_tracks))
        else:
            return self._search_album(provider, title, artist, tracks, min_tracks)

    @lru_cache()
    def song(self, provider, title, artist=''):
        RESULTS_TO_REVIEW = 4
        search = [lambda: self.lastfm.search_for_track(artist, title).get_next_page(),
                  lambda: self.shark.getResultsFromSearch(title, 'Songs')['result'],
                  lambda: brainz.search_recordings(title, artist=artist)['recording-list']][provider]
        Song = [LastSong, SharkSong, BrainzSong][provider]
        output = None
        try:
            output = search()
        except:
            return None
        if output:
            for i, result in enumerate(output):
                if i == RESULTS_TO_REVIEW:
                    break
                song = Song(result)
                if artist and diff(song.artist, artist) > 0.5:
                    continue
                if diff(song.name, title) < 0.5:
                    return song

        return None

    def download_tuple(self, data):
        try:
            return self.download_as(*data)
        except Exception as exc:
            logger.exception(exc)
            logger.debug('download of ' + repr(data) + ' failed')
            return ''

    def download_as(self, title, artist='', album='', track=0):
        '''Downloads song and set its tags to given title, artist, album'''
        logger.debug('in download(' + repr((title, artist, album, track)) + ')')
        title = strip_unprintable(title.strip())
        artist = strip_unprintable(artist.strip())
        album = strip_unprintable(album.strip())
        data = None
        providers = [vpleer.download, grooveshark.download]
        exc = None
        for download in providers:
            try:
                data = download(artist, title)
            except Exception as exc:
                logger.exception(exc)
            else:
                break
        else:
            return ''

        filename = str(track).zfill(2) + ' - ' + artist + '-' + title + '.mp3'  # + '__' + str(random.randint(100000, 999999))
        with open(filename, 'wb') as file:
            file.write(data)
            file.flush()
        del data
        tag = open_tag(filename)
        if not artist:
            artist = tag.artist.strip()
            logger.info("Setting new song's artist to " + artist)
        elif tag.artist.strip() and tag.artist.strip() != artist:
            logger.info('Original artist was ' + tag.artist.strip())
        if not title:
            title = tag.title.strip()
            logger.info("Setting new song's title to " + title)
        elif tag.title.strip() and tag.title.strip() != title:
            logger.info('Original title was ' + tag.title.strip())
        if not album:
            album = tag.album.strip()
            logger.info("Setting new song's album to " + album)
        elif tag.album.strip() and tag.album.strip() != album:
            logger.info('Original album was ' + tag.album.strip())
        if not track:
            track = tag.track
            logger.info("Setting new song's track to " + str(track))
        elif tag.track != track:
            logger.info('Original track was ' + str(tag.track))

        tag._frames.clear()
        tag.title = title
        tag.artist = artist
        tag.album = album
        tag.track = track
        tag.write()
        return filename

    @lru_cache()
    def generic(self, what, query, artist=None):
        result = None
        if what == 'track':
            result = (self.song(BRAINZ, query, artist=artist) or
                      self.song(LASTFM, query, artist=artist))
        elif what == 'album':
            result = (self.album(BRAINZ, query, artist=artist) or
                      self.album(LASTFM, query, artist=artist))
        elif what == 'artist':
            result = (self.artist(BRAINZ, query) or self.artist(LASTFM, query))
        if not result:
            raise NotFoundOnline
        else:
            return result

    def download_by_list(self, data):
        '''Downloads given songs in parallel'''
        try:
            return [self.download_tuple(song) for song in data]
            # with multiprocessing.Pool(processes=max(len(data) // 2, 2)) as pool:
                # return pool.map(self.download_tuple, data)
        except urllib.error.URLError as exc:
            print('Can not fetch songs')
            logger.exception(exc)
            return []
