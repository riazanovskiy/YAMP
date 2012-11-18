import random
import re
from functools import lru_cache
from pprint import pprint

import pylast
import musicbrainzngs as brainz

import grooveshark
import vpleer

from errors import SongNotFound, NotFoundOnline
from tags import open_tag
from misc import normalcase, improve_encoding, levenshtein, strip_unprintable


def diff(a, b):
    return levenshtein(normalcase(a), normalcase(b)) / min(len(a), len(b))


class OnlineData:
    def __init__(self):
        self.lastfm = pylast.LastFMNetwork('e494d3c2d1e99307336886c9e1f18af2',
                                           '989f1acfe251e590981d485ad9a82bd1')
        brainz.set_useragent('HYA', '1.2', 'http://vk.com')
        grooveshark.setup_connection()

    @lru_cache()
    def generic_search(self, what, query, artist=''):
        '''
           Returns propper name for album, artist or track queried.
           Arguments:
           what -- type of query. Must be 'album', 'artist' or 'track'.
           query -- text queried.

        '''
        query = strip_unprintable(query)
        artist = strip_unprintable(artist)
        assert (what in ['album', 'artist', 'track'])
        mb_methods = {'album': lambda x: brainz.search_releases(x, artist=artist),
                      'artist': brainz.search_artists,
                      'track': lambda x: brainz.search_recordings(x, artist=artist)}

        mb_results = {'album': ('release-list', 'title'),
                      'artist': ('artist-list', 'name'),
                      'track': ('recording-list', 'title')}

        lastfm_methods = {'album': self.lastfm.search_for_album,
                          'artist': self.lastfm.search_for_artist,
                          'track': lambda x: self.lastfm.search_for_track(artist, x)}

        modified = re.sub('\(.+\)', '', query)
        modified = re.sub('\[.+\]', '', modified)
        print('query', 'modified')
        print(query, modified)

        if query:
            try:
                result = mb_methods[what](query)
                if result:
                    result = result[mb_results[what][0]]
                    if result:
                        result = result[0][mb_results[what][1]]
                        if diff(result, query) < 0.5:
                            return result
                        else:
                            raise Exception()
            except:
                pass
            try:
                result = lastfm_methods[what](query).get_next_page()
                if result:
                    result = result[0].get_name(properly_capitalized=True)
                    if diff(result, query) < 0.5:
                        return result
                    else:
                        raise Exception()
            except:
                pass
            try:
                result = lastfm_methods[what](modified).get_next_page()
                if result:
                    result = result[0].get_name(properly_capitalized=True)
                    if diff(result, modified) < 0.5:
                        return result
                    else:
                        raise Exception()
            except:
                pass
            try:
                result = mb_methods[what](modified)
                if result:
                    result = result[mb_results[what][0]]
                    if result:
                        result = result[0][mb_results[what][1]]
                        if diff(result, modified) < 0.5:
                            return result
                        else:
                            raise Exception()
            except:
                pass

        raise NotFoundOnline()

    def download_as(self, title, artist='', album=''):
        '''Downloads song and set its tags to given title, artist, album'''
        title = strip_unprintable(title.strip())
        artist = strip_unprintable(artist.strip())
        album = strip_unprintable(album.strip())
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
        artist = strip_unprintable(artist)
        output = []

        results = self.lastfm.search_for_artist(artist).get_next_page()

        if results:
            if results[0].name != artist:
                print('Query:', artist, '; last.fm data:', results[0].name)
            songs = [i.item for i in results[0].get_top_tracks()]
            for i in songs:
                try:
                    output.append((improve_encoding(i.title),
                                                    improve_encoding(i.get_album().title),
                                                    '-1',
                                                    '0'))
                except:
                    pass
        results = grooveshark.singleton.getResultsFromSearch(artist, 'Artists')['result']

        if results:
            artist_id = int(results[0]['ArtistID'])
            artist_name = results[0]['ArtistName']
            if artist_name != artist:
                print('Query:', artist, '; grooveshark data:', artist_name)
            songs = grooveshark.singleton.artistGetAllSongsEx(artist_id)
            output += [(improve_encoding(i['Name']), improve_encoding(i['AlbumName']), i['TrackNum'], i['SongID']) for i in songs]

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

    def get_track_list(self, artist, album, min_count=0, known_tracks=[]):
        artist = strip_unprintable(artist)
        album = strip_unprintable(album)
        ##### MUSICBRAINZ
        # print('brainz')
        search = brainz.search_releases(album, artist=artist)['release-list']
        count = 0
        for i in search:
            if (normalcase(i['artist-credit-phrase']) == normalcase(artist) and
                normalcase(i['title']) == normalcase(album)):
                count += 1
                if count > 15:
                    print('No more!!!!!!!!1')
                    break
                # print(count)
                data = []
                for i in brainz.get_release_by_id(i['id'], includes='recordings')['release']['medium-list']:
                    data += i['track-list']
                tracks_brainz = [(i['position'], i['recording']['title']) for i in data]
                if len(tracks_brainz) >= min_count:
                    tracks_brainz = [(i[1],) for i in sorted(tracks_brainz)]
                    normalized = [normalcase(track) for track, in tracks_brainz]
                    for title in known_tracks:
                        if title not in normalized:
                            # print('Omitting because', title, 'is not found there')
                            break
                    else:
                        return tracks_brainz
                # else:
                    # print('Omitting', i['title'], 'because', len(tracks_brainz), ' < ', min_count)
        ##### LAST.FM
        # print('lastfm')
        search = self.lastfm.search_for_album(album)
        page = search.get_next_page()
        count = 0
        while page and count < 5:
            for i in page:
                if normalcase(i.artist.name) == normalcase(artist):
                    tracks_lastfm = [(i.title,) for i in i.get_tracks()]
                    if len(tracks_lastfm) >= min_count:
                        normalized = [normalcase(i) for i, in tracks_lastfm]
                        for title in known_tracks:
                            if title not in normalized:
                                # print('Omitting because', title, 'not found')
                                break
                        else:
                            return tracks_lastfm
                count += 1
                if count > 5:
                    break
            page = search.get_next_page()

        if known_tracks:
            return []

        ##### GROOVESHARK
        # print('grooveshark')
        search = grooveshark.singleton.getResultsFromSearch(artist, 'Artists')['result']
        for result in search:
            if normalcase(result['AlbumName']) == normalcase(album):
                found = result['AlbumID']
                data = grooveshark.singleton.albumGetAllSongs(found)
                tracks_grooveshark = [(i['TrackNum'] or '', improve_encoding(i['Name']) or '', i['SongID']) for i in data]
                if len(tracks_grooveshark) >= min_count:
                    tracks_grooveshark = [i[1:] for i in sorted(tracks_grooveshark)]
                    normalized = [normalcase(i) for i, j in tracks_grooveshark]
                    for title in known_tracks:
                        if title not in normalized:
                            # print('Omitting', result['AlbumName'], 'because', title, 'is not found there')
                            break
                    else:
                        return tracks_grooveshark
        return []

    def artist_of_album(self, album):
        album = strip_unprintable(album)
        search = self.lastfm.search_for_album(album)
        page = search.get_next_page()

        for i in page:
            if normalcase(i.title) == normalcase(album):
                return i.artist
        search = brainz.search_releases(album)['release-list']
        if search:
            return search[0]['artist-credit'][0]['artist']['name']
