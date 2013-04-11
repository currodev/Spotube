#!/usr/bin/python
# -*- coding: utf8 -*-

import cmd
import os
import sys
import threading
import string
import ConfigParser
import gdata.youtube
import gdata.youtube.service

from spotify.manager import (SpotifySessionManager, SpotifyContainerManager)

container_loaded = threading.Event()

class SpoTubeUI(cmd.Cmd, threading.Thread):

    prompt = "spotube> "

    def __init__(self, jukebox):
        cmd.Cmd.__init__(self)
        threading.Thread.__init__(self)
        self.jukebox = jukebox

    def run(self):
        container_loaded.wait()
        container_loaded.clear()
        try:
            self.cmdloop()
        finally:
            self.do_quit(None)

    def do_logout(self, line):
        self.jukebox.session.logout()

    def do_quit(self, line):
        self.jukebox.disconnect()
        print ("Goodbye!")
        return True

    def do_list(self, line):
        """ List the playlists, or the contents of a playlist """
        if not line:
            i = -1
            for i, p in enumerate(self.jukebox.ctr):
                if p.is_loaded():
                    print ("%3d %s" % (i, p.name()))
                else:
                    print ("%3d %s" % (i, "loading..."))
            print ("%3d Starred tracks" % (i + 1,))

        else:
            try:
                p = int(line)
            except ValueError:
                print ("that's not a number!")
                return
            if p < 0 or p > len(self.jukebox.ctr):
                print ("That's out of range!")
                return
            print ("Listing playlist #%d" % p)
            if p < len(self.jukebox.ctr):
                playlist = self.jukebox.ctr[p]
            else:
                playlist = self.jukebox.starred
            for i, t in enumerate(playlist):
                if t.is_loaded():
                    print ("%3d %s - %s" % (
                        i, t.artists()[0].name(), t.name()))
                else:
                    print ("%3d %s" % (i, "loading..."))

    def do_export_list(self, line):
        """ Export the content of a playlist to a YouTube playlist """
        if not line:
            print ("Specify a number")
            return
        line_a = line.split()
        line = line_a[0]
        if len(line_a) == 1:
          yt_playlist_name = get_st_playlist_name()
        else:
          yt_playlist_name = line_a[1]
        try:
            p = int(line)
        except ValueError:
            print ("that's not a number!")
            return
        if p < 0 or p > len(self.jukebox.ctr):
            print ("That's out of range!")
            return
        print ("Exporting playlist #%d" % p)
        if p < len(self.jukebox.ctr):
            playlist = self.jukebox.ctr[p]
        else:
            playlist = self.jukebox.starred
        yt_username, yt_email, yt_password, yt_developer_key, yt_country_code = get_youtube_credentials()
        try:
          yt = YouTube(yt_username, yt_email, yt_password, yt_developer_key, yt_country_code)
          yt.yt_login()
        except Exception as e:
          print ("[YouTube] " + e.args[0])
          self.disconnect()
        if not yt.yt_init_playlist(yt_playlist_name):
          self.disconnect()
          return
        print ("[Spotify] Loading playlist...")

        for i, t in enumerate(playlist):
            if t.is_loaded():
              query_str = clean_title(t.artists()[0].name() + " " +  t.name())
              yt_video_id = yt.yt_query_video(query_str)
              try:
                yt.yt_add_video(yt_video_id)
              except Exception as e:
                print ("[YouTube] [EE] Can't add video " + yt_video_id)
                print (e)
            else:
                print ("%3d %s" % (i, "loading..."))

    def do_shell(self, line):
        self.jukebox.shell()

    do_ls = do_list
    do_EOF = do_quit

## container calllbacks ##
class SpoTubeContainerManager(SpotifyContainerManager):
    def container_loaded(self, c, u):
        container_loaded.set()


class SpoTube(SpotifySessionManager):

    appkey_file = os.path.join(os.path.dirname(__file__), 'spotify_appkey.key')

    def __init__(self, *a, **kw):
        SpotifySessionManager.__init__(self, *a, **kw)
        self.ui = SpoTubeUI(self)
        self.ctr = None
        self.container_manager = SpoTubeContainerManager()
        print ("[Spotify] Logging in, please wait...")

    def logged_in(self, session, error):
        if error:
          print ("[Spotify] " + error)
          return
        print ("[Spotify] Logged in!")
        self.ctr = session.playlist_container()
        self.container_manager.watch(self.ctr)
        self.starred = session.starred()
        if not self.ui.is_alive():
            self.ui.start()

    def logged_out(self, session):
        print ("[Spotify] Logged out!")

    def shell(self):
        import code
        shell = code.InteractiveConsole(globals())
        shell.interact()

class YouTube():

  def __init__(self, username, email, password, developer_key, country_code):
    self.username = username
    self.email = email
    self.password = password
    self.developer_key = developer_key
    self.country_code = country_code
    self.yt_service = None
    self.playlist_uri = None

  def yt_login(self):
    print ("[YouTube] Login...")
    self.yt_service = gdata.youtube.service.YouTubeService()
    self.yt_service.developer_key = self.developer_key
    self.yt_service.email= self.email
    self.yt_service.password = self.password
    self.yt_service.ProgrammaticLogin()

  def yt_init_playlist(self, yt_playlist_name):
    print ("[YouTube] Creating playlist...")
    playlist_feed = self.yt_service.GetYouTubePlaylistFeed(username=self.username)

    for playlist in playlist_feed.entry:
      if playlist.title.text == yt_playlist_name: 
        old_playlist = self.yt_service.DeletePlaylist(playlist.id.text)
        if isinstance(old_playlist, gdata.youtube.YouTubePlaylistEntry):
          print ("[YouTube] Old playlist deleted")
  
    spotube_playlist = self.yt_service.AddPlaylist(yt_playlist_name, "SpoTube playlist")
    if isinstance(spotube_playlist, gdata.youtube.YouTubePlaylistEntry):
      self.playlist_uri = spotube_playlist.feed_link[0].href
      print ("[YouTube] Playlist " + yt_playlist_name + " created")
      return True
    else:
      print ("[YouTube] ERROR")
      return False          

  def yt_query_video(self, query_str):
    print ("--------------------------------------")
    print ("[YouTube] Searching " + query_str)
    query = gdata.youtube.service.YouTubeVideoQuery()
    query.vq = query_str
    query.orderby = "relevance"
    query.restriction = self.country_code
    feed = self.yt_service.YouTubeQuery(query)
    video_name = feed.entry[0].media.title.text
    print ("[YouTube] Adding " + video_name)
    video_id = feed.entry[0].id.text.split("/")[-1]
    return video_id

  def yt_add_video(self, video_id):     
    playlist_video_entry = self.yt_service.AddPlaylistVideoEntryToPlaylist(self.playlist_uri, video_id)
    if isinstance(playlist_video_entry, gdata.youtube.YouTubePlaylistVideoEntry):
      print ("[YouTube] Video " + video_id + " added")

def get_youtube_credentials():
  return yt_username, yt_email, yt_password, yt_developer_key, yt_country_code

def get_st_playlist_name():
  return st_playlist_name

def clean_title(s):
  return filter(lambda x: x in string.printable, s)

def clean_config(s):
  if s.startswith('"') and s.endswith('"'):
    return s[1:-1]

if __name__ == '__main__':

  config = ConfigParser.ConfigParser()
  config.read("spotube.cfg")
  
  st_playlist_name = clean_config(config.get("spotube", "playlist_name"))
  sp_username = clean_config(config.get("spotify", "username"))
  sp_password = clean_config(config.get("spotify", "password"))
  yt_username = clean_config(config.get("youtube", "username"))
  yt_email = clean_config(config.get("youtube", "email"))
  yt_password = clean_config(config.get("youtube", "password"))
  yt_developer_key = clean_config(config.get("youtube", "developer_key"))
  yt_country_code = clean_config(config.get("youtube", "country_code"))

  session_m = SpoTube(sp_username, sp_password, True)
  session_m.connect()
