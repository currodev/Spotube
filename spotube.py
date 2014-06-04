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
from time import gmtime, strftime
import re
from spotify.manager import (SpotifySessionManager, SpotifyContainerManager)

## YOUTUBE API
import httplib2

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the Google Cloud Console at
# https://cloud.google.com/console.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets

CLIENT_SECRETS_FILE = "client_secrets.json"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

%s

with information from the Cloud Console
https://cloud.google.com/console

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
    CLIENT_SECRETS_FILE))

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account.
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

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
        """ export_playlist <number> [<name yt playlist>] [update]
        Export playlist with <number> to a youtuble playlist called <name yt playlist> """
        if not line:
            print ("Specify a number")
            return
        line_a = line.split()
        line = line_a[0]
        if len(line_a) == 1:
          yt_playlist_name = get_st_playlist_name()
        else:
          yt_playlist_name = line_a[1]
        update = 0
        if len(line_a) == 3 and line_a[2] == "update":
            update = 1
        try:
            p = int(line)
        except ValueError:
            print ("That's not a number!")
            return
        if p < 0 or p > len(self.jukebox.ctr):
            print ("That's out of range!")
            return
        print ("Exporting playlist #%d" % p)
        if p < len(self.jukebox.ctr):
            playlist = self.jukebox.ctr[p]
        else:
            playlist = self.jukebox.starred
        yt_country_code = get_country_code()
        try:
          yt = YouTube(yt_country_code)
          yt.yt_login()
        except Exception as e:
          print ("[YouTube] [EE] " + e.args[0])
          debug("EE", sys.exc_info())
          return
        if not yt.yt_init_playlist(yt_playlist_name, update):
          print ("[YouTube] [EE] Can't create playlist " + yt_playlist_name);
          return

        print ("[Spotify] Loading playlist...")

        for i, t in enumerate(playlist):
            if t.is_loaded():
                query_str = t.artists()[0].name() + " " +  t.name()
                yt_video_id = yt.yt_query_video(query_str)
                if yt_video_id:
                    try:
                        if (update):
                            if not (yt.yt_search_video_in_playlist(yt_video_id)):
                                yt.yt_add_video(yt_video_id)
                        else:
                            yt.yt_add_video(yt_video_id)
                    except Exception as e:
                        print ("[YouTube] [EE] Can't add video " + yt_video_id)
                        print (e)
                        debug("EE", sys.exc_info())
                        video_title = t.artists()[0].name() + " - " + t.name()
            else:
                print ("%3d %s" % (i, "loading..."))
          
    def do_shell(self, line):
        self.jukebox.shell()

    do_ls = do_list
    do_EOF = do_quit

## container callbacks ##
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

  def __init__(self, country_code):
    self.country_code = country_code
    self.yt_service = None
    self.playlist_id = None

  def yt_login(self):
    print ("[YouTube] Login...")
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=YOUTUBE_SCOPE,
      message=MISSING_CLIENT_SECRETS_MESSAGE)

    storage = Storage("%s-oauth2.json" % "spotube")
    credentials = storage.get()
    if credentials is None or credentials.invalid:
      credentials = run(flow, storage)

    self.yt_service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
      http=credentials.authorize(httplib2.Http()))

  def yt_init_playlist(self, yt_playlist_name, update=0):
    print ("[YouTube] Creating playlist...")
    search_response = self.yt_service.playlists().list(
        part="snippet",
        mine="true",
        ).execute()

    for search_result in search_response.get("items", []):
        if (search_result["snippet"]["title"] == yt_playlist_name):
            if (update):
                self.playlist_id = search_result["id"]
                return True
            self.yt_service.playlists().delete(
                id=search_result["id"],
                ).execute()

    playlists_insert_response = self.yt_service.playlists().insert(
    part="snippet,status",
    body=dict(
      snippet=dict(
        title=yt_playlist_name,
        description="SpoTube playlist"
      ),
      status=dict(
        privacyStatus="private"
      )
    )).execute()
    self.playlist_id = playlists_insert_response["id"]
    return True
    
  def yt_get_playlist_feed(self, username):
    return self.yt_service.GetYouTubePlaylistFeed(username=username)

  def yt_query_video(self, query_str):
    print ("--------------------------------------")
    print ("[YouTube] Searching " + query_str)
    search_response = self.yt_service.search().list(
      q=query_str,
      part="id,snippet",
      #type="video",
      safeSearch="none",
      regionCode=self.country_code,
      order="relevance",
      maxResults=10
    ).execute()
    totalResults = search_response.get("pageInfo")["totalResults"]
    if totalResults > 0:
      try:
        i=0
        firstResultName = ""
        firstResultId = ""
        for search_result in search_response.get("items", []):
          if i == 0:
            firstResultName = search_result["snippet"]["title"]
            firstResultId = search_result["id"]["videoId"]
          if search_result["snippet"]["channelTitle"].endswith("VEVO"):
            print ("[YouTube] Adding " + search_result["snippet"]["title"])
            return search_result["id"]["videoId"]
          i+=1
        print ("[YouTube] Adding " + firstResultName)
        return firstResultId
      except:
        print ("[YouTube] [EE] No video found for this track")
        return False
    else:
      print ("[YouTube] [EE] No video found for this track")
      return False

  def yt_search_video_in_playlist(self, video_id):
    search_video_request=self.yt_service.playlistItems().list(
        part="snippet",
        playlistId=self.playlist_id,
        videoId=video_id,
        ).execute()
    totalResults = search_video_request.get("pageInfo")["totalResults"]
    if totalResults > 0:
        print("[YouTube] Video already in playlist")
        return True
    return False

  def yt_add_video(self, video_id):
    add_video_request=self.yt_service.playlistItems().insert(
    part="snippet",
    body={
      'snippet': {
        'playlistId': self.playlist_id, 
        'resourceId': {
          'kind': 'youtube#video',
          'videoId': video_id
        }
                #'position': 0
      }
    }).execute()
    print ("[YouTube] Video " + video_id + " added")

  def yt_get_video_title(self, video_id):
    entry = self.yt_service.GetYouTubeVideoEntry(video_id=video_id)
    return entry.media.title.text

  def yt_set_playlist_uri(self, playlist):
    self.playlist_uri = playlist.feed_link[0].href
    

def get_country_code():
  return yt_country_code

def get_st_playlist_name():
  return st_playlist_name

# @deprecated
def clean_title(s):
  return filter(lambda x: x in string.printable, s)

def clean_config(s):
  if s.startswith('"') and s.endswith('"'):
    return s[1:-1]

def debug(level, text):
  f = open("error.log", "ab")
  f.write("[" + level + "] " + str(text) + "\n")
  f.close()

if __name__ == '__main__':

  config = ConfigParser.ConfigParser()
  config.read("spotube.cfg")
  
  st_playlist_name = clean_config(config.get("spotube", "playlist_name"))
  sp_username = clean_config(config.get("spotify", "username"))
  sp_password = clean_config(config.get("spotify", "password"))
  yt_country_code = clean_config(config.get("youtube", "country_code"))

  session_m = SpoTube(sp_username, sp_password, True)
  session_m.connect()
