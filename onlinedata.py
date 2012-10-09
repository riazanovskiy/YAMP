import pylast
import musicbrainzngs as brainz
from functools import lru_cache


class OnlineData:
    def __init__(self):
        self.lastfm = pylast.LastFMNetwork('e494d3c2d1e99307336886c9e1f18af2',
                                           '989f1acfe251e590981d485ad9a82bd1')
        # self.librefm = pylast.LibreFMNetwork()
        brainz.set_useragent('yamp', '0.00', 'http://example.com')

    @lru_cache()
    def search_artist(self, artist):
        if not artist:
            return ''
        result = brainz.search_artists(artist)
        if result:
            result = result['artist-list']
            if result:
                return result[0]['name']
        result = self.lastfm.search_for_artists(artist).get_next_page()
        if result:
            return result[0].get_name(properly_capitalized=True)
        return artist
