import pylast
import musicbrainzngs as brainz
from functools import lru_cache

import grooveshark
import vpleer
import random

from errors import SongNotFound, NotFoundOnline
from tags import open_tag


class OnlineData:
    '''This class provides access to online music datebases, currently Musicbrainz and Last.fm'''
    def __init__(self):
        self.lastfm = pylast.LastFMNetwork('e494d3c2d1e99307336886c9e1f18af2',
                                           '989f1acfe251e590981d485ad9a82bd1')
        brainz.set_useragent('yamp', '0.00', 'http://example.com')

    @lru_cache()
    def generic_search(self, what, query):
        '''
           Returns propper name for album, artist or track queried.
           Arguments:
           what -- type of query. Must be 'album', 'artist' or 'track'.
           query -- text queried.

        '''

        assert (what in ['album', 'artist', 'track'])
        mb_methods = {'album': brainz.search_releases,
                      'artist': brainz.search_artists,
                      'track': brainz.search_recordings}
        mb_results = {'album': ('release-list', 'title'),
                      'artist': ('artist-list', 'name'),
                      'track': ('recording-list', 'title')}
        lastfm_methods = {'album': self.lastfm.search_for_album,
                          'artist': self.lastfm.search_for_artist,
                          'track': lambda x: self.lastfm.search_for_track('', x)}
        if query:
            try:
                result = mb_methods[what](query)
                if result:
                    result = result[mb_results[what][0]]
                    if result:
                        return result[0][mb_results[what][1]]
            except:
                pass
            try:
                result = lastfm_methods[what](query).get_next_page()
                if result:
                    return result[0].get_name(properly_capitalized=True)
            except:
                pass

        raise NotFoundOnline()

    def download_as(self, title, artist='', album=''):
        '''Downloads song and set its tags to given title, artist, album'''
        title = title.strip()
        artist = artist.strip()
        album = album.strip()
        data = None
        ways = [grooveshark.download, vpleer.download]
        for download in ways:
            try:
                data = download(artist + ' ' + title)
            except SongNotFound:
                pass
            else:
                break
        else:
            raise SongNotFound
        filename = artist + '-' + title + '__' + str(random.randint(100500))
        file = open(filename, 'w')
        file.write(data)
        tag = open_tag(filename)
        artist = artist or tag.artist.strip()
        title = title or tag.title.strip()
        album = album or tag.album.strip()
        tag._frames.clear()
        tag.title = title
        tag.artist = artist
        tag.album = album
        tag.write()
        return filename

    def top_tracks(self, artist):
        pass
