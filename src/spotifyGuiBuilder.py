# spotifyGuiBuilder.py
#
# Copyright 2020 Merlin Danner
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import threading

from functools import reduce

from xdg import XDG_CACHE_HOME

import gi
from gi.repository import Gtk, GdkPixbuf, GLib, GObject, Pango

from .coverArtLoader import CoverArtLoader
from .spotify import Spotify as sp

class TrackListRow(Gtk.ListBoxRow):

	def __init__(self, trackID, **kwargs):
		super().__init__(**kwargs)

class PlaylistsListRow(Gtk.ListBoxRow):

	def __init__(self, playlistID, **kwargs):
		super().__init__(**kwargs)
		self.playlistID = playlistID

	def getPlaylistID(self):
		return self.playlistID

class SpotifyGuiBuilder:

	def __init__(self):

		self.coverArtLoader = CoverArtLoader()
		self.currentPlaylistID = ''

	def buildTrackEntry(self, trackResponse):
		track = trackResponse['track']
		row = TrackListRow(track['id'])
		hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		try:
			imageUrl = track['album']['images'][0]['url']
			coverArt = self.coverArtLoader.getLoadingImage()
			hbox.pack_start(coverArt, False, True, 5)
			self.coverArtLoader.asyncUpdateAlbumCover(hbox, coverArt, url=imageUrl, ID=track['album']['id'])
		except IndexError:
			coverArt = self.coverArtLoader.getErrorImage()
			hbox.pack_start(coverArt, False, True, 5)
			print("Failed retrieveing the imageUrl for the track: " + str(track))
		trackNameString = track['name']
		artistString = reduce(lambda a, b: {'name': a['name'] + ", " + b['name']},
					track['artists'][1:],
					track['artists'][0]
					)['name']
		trackLabelString = '<b>' + GLib.markup_escape_text(trackNameString) + '</b>' + '\n' + GLib.markup_escape_text(artistString)
		trackLabel = Gtk.Label(xalign=0)
		trackLabel.set_max_width_chars(64)
		trackLabel.set_line_wrap(True)
		trackLabel.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
		trackLabel.set_markup(trackLabelString)
		hbox.pack_end(trackLabel, True, True, 0)
		row.add(hbox)
		return row

	def clearList(self, listToClear):
		for child in listToClear.get_children():
			listToClear.remove(child)


	def asyncLoadPlaylistTracks(self, tracksList, playlistID, resumeEvent, stopEvent):
		if self.currentPlaylistID == playlistID:
			resumeEvent.set()
			return
		self.currentPlaylistID = playlistID

		self.clearList(tracksList)

		def addTrackEntry(track):
			trackEntry = self.buildTrackEntry(track)
			tracksList.add(trackEntry)

		def loadPlaylistTracks():
			allTracks = []
			offset = 0
			pageSize = 100
			keepGoing = True
			while keepGoing:
				tracksResponse = sp.get().playlist_tracks(
					playlist_id=playlistID,
					fields='items(track(id,name,artists(name),album(id,images))),next',
					limit=pageSize,
					offset=offset)
				keepGoing = tracksResponse['next'] != None
				offset += pageSize
				allTracks += tracksResponse['items']

			def addAllTrackEntries():
				try:
					counter = 0
					for track in allTracks:
						if stopEvent.is_set():
							break
						GLib.idle_add(addTrackEntry, track)
						counter += 1
						if counter == 10:
							GLib.idle_add(tracksList.show_all)
						counter %= 10
						GLib.idle_add(tracksList.show_all)
				finally:
					resumeEvent.set()

			addAllTrackEntries()

		thread = threading.Thread(target=loadPlaylistTracks)
		thread.start()

	def asyncLoadPlaylists(self, playlistsList):
		def addPlaylistEntry(playlist):
			row = PlaylistsListRow(playlist['id'])
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
			imageUrl = playlist['images'][0]['url']
			coverArt = self.coverArtLoader.getLoadingImage()
			hbox.pack_start(coverArt, False, True, 5)
			self.coverArtLoader.asyncUpdatePlaylistCover(hbox, coverArt, url=imageUrl, ID=playlist['id'])
			nameLabel = Gtk.Label(playlist['name'], xalign=0)
			nameLabel.set_max_width_chars(32)
			nameLabel.set_line_wrap(True)
			nameLabel.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
			hbox.pack_end(nameLabel, True, True, 0)
			row.add(hbox)
			playlistsList.add(row)
			playlistsList.show_all()

		def loadPlaylists():
			allPlaylists = []
			offset = 0
			pageSize = 50
			keepGoing = True
			while keepGoing:
				playlistsResponse = sp.get().current_user_playlists(limit=pageSize, offset=offset)
				keepGoing = playlistsResponse['next'] != None
				offset += pageSize
				allPlaylists += playlistsResponse['items']

			def addAllPlaylistEntries():
				for playlist in allPlaylists:
					GLib.idle_add(addPlaylistEntry, playlist)

			addAllPlaylistEntries()

		thread = threading.Thread(target=loadPlaylists)
		thread.start()
