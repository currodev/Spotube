Spotube
=======

Convert Spotify playlists into YouTube ones.

Based on Jukebox (PySpotify).

Dependencies
------------

* Python 2.7
* LibSpotify
* PySpotify 
* GData (Python API Google)

* Spotify Premium Account
* Google OAuth 2.0 Client ID

Installation
------------

* LibSpotify
 * Download https://developer.spotify.com/technologies/libspotify/
 * Extract and run

   <code># make install prefix=/usr/local</code>

* PySpotify
 * Download http://pyspotify.mopidy.com 
 * Extract and run

   <code># python setup.py install</code>

* GData
 * Download http://code.google.com/p/gdata-python-client/downloads/list
 * Extract and run

   <code># python setup.py install</code>

* Spotify Premium Account
 * You will need to request an application key at the developer website http://developer.spotify.com/ before being able to run it.
 * Place **spotify_appkey.key** in the same folder that spotube.py

* Google OAuth 2.0 Client ID
 * https://cloud.google.com/console
 * Create a web application and download client secrets file.

Configuration
-------------

* Complete **spotube.cfg** with your Spotify and YouTube credentials.

Run
---

* Run

  <code>$ python spotube.py</code>

* List Spotify playlist
  <code>spotube> ls</code>

* Export Spotify playlist
  <code>spotube> export_playlist spotify_playlist_number [youtube_playlist_name] [update]</code>

License
-------

* MIT License
