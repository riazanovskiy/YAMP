import random
from functools import lru_cache
from pprint import pprint

import pylast
import musicbrainzngs as brainz

import grooveshark
import vpleer

from errors import SongNotFound, NotFoundOnline
from tags import open_tag
from misc import normalcase


class OnlineData:
    '''This class provides access to online music datebases, currently Musicbrainz and Last.fm'''
    def __init__(self):
        self.lastfm = pylast.LastFMNetwork('e494d3c2d1e99307336886c9e1f18af2',
                                           '989f1acfe251e590981d485ad9a82bd1')
        brainz.set_useragent('yamp', '0.00', 'http://example.com')
        grooveshark.setup_connection()

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
            raise SongNotFound()
        filename = artist + '-' + title + '__' + str(random.randint(100500))
        file = open(filename, 'w')
        file.write(data)
        tag = open_tag(filename)
        artist = artist or tag.artist.strip()
        title = title or tag.title.strip()
        album = album or tag.album.strip()
        track = tag.track
        tag._frames.clear()
        tag.title = title
        tag.artist = artist
        tag.album = album
        tag.track = track
        tag.write()
        return filename

    def get_tracks_for_artist(self, artist):
        output = []

        results = self.lastfm.search_for_artist(artist).get_next_page()

        if results:
            if results[0].name != artist:
                print('Query:', artist, '; last.fm data:', results[0].name)
            songs = [i.item for i in results[0].get_top_tracks()]
            for i in songs:
                try:
                    output.append((i.title, i.get_album().title, '-1', '0'))
                except:
                    pass
        results = grooveshark.singleton.getResultsFromSearch(artist, 'Artists')['result']

        if results:
            artist_id = int(results[0]['ArtistID'])
            artist_name = results[0]['ArtistName']
            if artist_name != artist:
                print('Query:', artist, '; grooveshark data:', artist_name)
            songs = grooveshark.singleton.artistGetAllSongsEx(artist_id)
            output += [(i['Name'], i['AlbumName'], i['TrackNum'], i['SongID']) for i in songs]

        # results = brainz.search_artists(artist)['artist-list']
        # if results:
        #     artist_id = results[0]['id']
        #     artist_name = results[0]['name']
        #     if artist_name != artist:
        #         print('Query:', artist, '; musicbrainz data:', artist_name)
        #     songs = brainz.get_artist_by_id(artist_id, includes=['recordings'])
        #     songs = songs['artist']['recording-list']
        #     for i in songs:
        #         search = brainz.get_recording_by_id(i['id'], includes=['releases'])
        #         output.append((i['title'], i[search['recording']['release-list'][0]['title']],
        #                        '-1', '0'))

        return output

    def get_track_list(self, artist, album):
        #### LAST.FM
        search = self.lastfm.search_for_album(album)
        page = search.get_next_page()
        found = None
        while page:
            for i in page:
                if normalcase(i.artist) == normalcase(artist):
                    found = i
                    break
            page = search.get_next_page()
        if found:
            tracks_lastfm = [i.title for i in found.get_tracks()]
            if tracks_lastfm:
                return tracks_lastfm
        #### MUSICBRAINZ
        found = None
        search = brainz.search_releases(album, artist=artist)['release-list']
        for i in search:
            if (normalcase(i['artist-credit-phrase']) == normalcase(artist) and
                normalcase(i['title']) == normalcase(album)):
                found = i['id']
                break
        if found:
            data = brainz.get_release_by_id(found, includes='recordings')['release']['medium-list'][0]['track-list']
            tracks_brainz = [(i['position'], i['recording']['title']) for i in data]
            tracks_brainz = [i[1] for i in sorted(tracks_brainz)]
            if tracks_brainz:
                return tracks_brainz

        found = None
        #### GROOVESHARK
        search = grooveshark.singleton.getResultsFromSearch(artist, 'Artists')['result']
        for i in search:
            if normalcase(i['AlbumName']) == normalcase(album):
                found = i['AlbumID']
                break
        if found:
            data = grooveshark.singleton.albumGetAllSongs(found)
            tracks_grooveshark = [(i['TrackNum'], i['Name'], i['SongID']) for i in data]
            tracks_grooveshark = [i[1:] for i in sorted(tracks_grooveshark)]
            return tracks_grooveshark
        return []
