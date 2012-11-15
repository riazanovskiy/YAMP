import warnings
warnings.simplefilter('ignore')
import cmd
import os
import glob
import readline

import yamp
from misc import verify_dir


class YampShell(cmd.Cmd):
    prompt = '$ ' if os.name == 'nt' else '> '
    file = None
    doc_header = 'This is yet another music player.'
    _artists = []
    _albums = []

    def albums(self):
        return self._albums or database.get_albums_list()

    def artists(self):
        return self._albums or database.get_artists_list()

############# import ######################

    def do_import(self, args):
        folders = [j for j in (os.path.abspath(i) for i in args.split()) if os.path.isdir(j)]
        if not folders:
            print('Nothing to import.')
        for i in folders:
            database.import_folder(i)

    def help_import(self):
        print('import /directory/name ...')
        print('Imports selected directory to yamp. This does not actually move files.')

    def complete_import(self, text, line, begidx, endidx):
        return (glob.glob(text + '*') + [None])

############# move ######################

    def do_move(self, args):
        print('Moving all music files. Be patient, this can take some time.')
        database.move_files()

    def help_move(self):
        print('Moves all the files to corresponding folders.')

############# show ######################

    def do_show(self, args):
        args = args.strip()
        if args == 'albums':
            print('\n'.join(self.albums()))
        elif args == 'artists':
            print('\n'.join(self.artists()))
        elif args == 'all':
            database.pretty_print()

    def help_show(self):
        print('show artists|albums|all')
        print('show artist artistname')
        print('show album albumname')
        print('show tracks artist|album')
        print('Shows different parts of library.')

    def complete_show(self, text, line, begidx, endidx):
        completion = ['artists', 'albums', 'all']
        return [i for i in completion if i.startswith(text)] + [None]

############# more ######################

    def do_more(self, args):
        args = args.strip()

        if args and args[0] == '@' or args in self.albums():
            if args[0] == '@':
                args = args[1:]
            artist = database.get_artist_of_album(args)
            print('Fetching more songs from album', args, 'by', artist)
            database.fill_album(artist, args)
        else:
            print('Fetching more songs by', args)
            database.add_tracks_for_artist(args)

    def help_more(self):
        print('more artist|album')
        print('more @album')
        print('This will add more songs of to library. Use @ to specify album.')

    def complete_more(self, text, line, begidx, endidx):
        pref = line[5:]
        while pref and pref[0] == ' ':
            pref = pref[1:]
            begidx -= 1

        if pref and pref[0] == '@':
            if begidx == 5:
                return ['@' + i for i in self.albums() if i.startswith(pref[1:])]
            else:
                return [i[begidx - 6:] for i in self.albums() if i.startswith(pref[1:])]
        else:
            return ([i[begidx - 5:] for i in self.albums() if i.startswith(pref)] +
                    [i[begidx - 5:] for i in self.artists() if i.startswith(pref)])

    def do_EOF(self, args):
        print()
        print('Exiting')
        return True

if __name__ == '__main__':
    accept = False
    try:
        # while (not accept):
            # path = os.path.abspath(input('Enter main path to music library: '))
            # accept = (input('Path is ' + path + ' (yes/no) ') == 'yes')
        path = '/home/dani/yamp'
        verify_dir(path)
        database = yamp.Database(path)
        readline.set_completer_delims(' \t\n;')
        YampShell().cmdloop()
    except Exception as exc:
        print(exc)
        print()
        print('Exiting')
