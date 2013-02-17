# import warnings
# warnings.simplefilter('ignore')
import os

import readline

import cmd
import colorama
import glob

import yamp
from misc import verify_dir
from log import logger


def get_yn_promt(promt):
    ans = input(promt)
    while ans not in ['y', 'n', '']:
        ans = input(promt)
    return ans == 'y'


class YampShell(cmd.Cmd):
    prompt = '$ ' if os.name == 'nt' else '> '
    file = None
    doc_header = 'This is yet another music player.'
    _artists = []
    _albums = []

    def albums(self):
        self._albums = self._albums or list(database.get_albums_list())
        return self._albums

    def artists(self):
        self._artists = self._artists or list(database.get_artists_list())
        return self._artists

    def _complete(self, line, begidx):
        command = len(line.split()[0]) + 1
        pref = line[command:]
        while pref and pref[0] == ' ':
            pref = pref[1:]
            begidx -= 1

        if pref:
            if pref[0] == '#':
                if begidx == command:
                    return ['#' + i for i in self.albums() if i.startswith(pref[1:])]
                else:
                    return [i[begidx - command - 1:] for i in self.albums() if i.startswith(pref[1:])]
            elif pref[0] == '@':
                if begidx == command:
                    return ['@' + i for i in self.artists() if i.startswith(pref[1:])]
                else:
                    return [i[begidx:] for i in self.artists() if i.startswith(pref[1:])]
        return ([i[begidx - command:] for i in self.albums() if i.startswith(pref)] +
                [i[begidx - command:] for i in self.artists() if i.startswith(pref)])

############# import ########################################################################################

    def do_import(self, args):
        args = os.path.abspath(args.strip())
        if os.path.exists(args):
            if os.path.isdir(args):
                database.import_folder(args)
            elif os.path.isfile(args):
                database.import_file(args)
                database.sql.commit()
            database.remove_extensions_from_tracks()
            database.track_numbers()
            database.generic_correction('artist')
            database.generic_correction('album')
            database.generic_correction('track')
            self._albums = []
            self._artists = []
        else:
            print('Nothing to import.')

    def help_import(self):
        print('import /directory/name ...')
        print('Imports selected directory to yamp. This does not actually move files.')

    def complete_import(self, text, line, begidx, endidx):
        return (glob.glob(text + '*') + [None])

############# move ########################################################################################

    def do_move(self, args):
        if input('Are you sure? ') == 'y':
            print('Moving all music files. Be patient, this can take some time.')
            database.move_files()
            database.writeout()

    def help_move(self):
        print('Moves all the files to corresponding folders.')

############# show ########################################################################################

    def do_show(self, args):
        args = args.strip()
        if not args:
            database.pretty_print()
        elif args == '@':
            print('\n'.join(sorted(self.artists())))
            return
        elif args == '#':
            print('\n'.join(sorted(self.albums())))
            return
        elif args[0] == '@':
            database.pretty_print(artist=args[1:])
            return
        elif args[0] == '#':
            database.pretty_print(album=args[1:])
            return
        elif args in self.albums():
            database.pretty_print(album=args)
            return
        elif args in self.artists():
            database.pretty_print(artist=args)
            return

    def help_show(self):
        print('show')
        print('show @artist')
        print('show #album')
        print('Shows different parts of library.')

    def complete_show(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# more ########################################################################################

    def do_more(self, args):
        args = args.strip()

        if not args:
            return
        do_artist = bool(args[0] == '@' or args in self.artists())
        do_album = bool(args[0] == '#' or args in self.albums())

        if args[0] in '@#':
            args = args[1:]

        if do_album == do_artist:
            do_album = False
            do_artist = True

        assert (do_artist != do_album)

        if do_album:
            artist = database.get_artist_of_album(args)
            print('Fetching more songs from album', args, 'by', artist)
            database.fill_album(artist, args)
        else:
            print('Fetching more songs by', args)
            database.fetch_tracks_for_artist(args)
        self._artists = []
        self._albums = []

    def help_more(self):
        print('more artist|album')
        print('more #album')
        print('more @artist')
        print('This will add more songs of to library. Use # to specify album. Use @ to specify artist.')

    def complete_more(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# translit ########################################################################################
    def help_translit(self):
        print('translit artist|album')
        print('translit #album')
        print('translit @artist')
        print('Заменит транслит в названиях')

    def complete_translit(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

    def do_translit(self, args):
        args = args.strip()
        if args:
            self._artists = []
            self._albums = []
            if args[0] == '@':
                database.transliterate('artist', args[1:], artist='')
                return
            elif args[0] == '#':
                database.transliterate_album(args[1:])
                return
            elif args in self.albums():
                database.transliterate_album(args)
                return
            elif args in self.artists():
                database.transliterate('artist', args, artist='')
                return

############# fetch ########################################################################################
    def help_fetch(self):
        print('fetch [count]')
        print("This will fetch mp3 file for songs which don't have one.")
        print('This will fetch up to count files or all of them if count is not specified')

    # def complete_fetch(self, text, line, begidx, endidx):
        # return self._complete(line, begidx)

    def do_fetch(self, args):
        args = args.strip()
        if args:
            try:
                count = int(args)
            except:
                print('You should specify a number')
                return
        else:
            count = 0
        database.fetch_data(count)
############# EOF ########################################################################################

    def do_EOF(self, args):
        print()
        print('Exiting')
        return True

    def emptyline(self):
        pass

if __name__ == '__main__':
    colorama.init()
    accept = False
    path = 'C:\yamp'
    while not accept:
        path = os.path.abspath(input('Enter main path to music library: '))
        prompt = input('Path is ' + path + ' (yes/no) ')
        if prompt == 'no':
            path = os.path.abspath(input('Enter main path to music library: '))
        accept = (prompt == 'yes' or prompt == 'y')
    verify_dir(path)
    database = yamp.Database(path)
    logger.info('Started')
    readline.set_completer_delims(' \t\n;')
    # readline.parse_and_bind("tab: complete")
    YampShell(completekey='tab').cmdloop('')
