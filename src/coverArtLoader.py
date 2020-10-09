# coverArtLoader.py
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

import threading
import os
from xdg import BaseDirectory

import requests
import gi
from gi.repository import Gtk, GdkPixbuf, GLib

from .config import Config

class CoverArtLoader:

	def __init__(self):
		self.imageSize = 60

	# GTK
	def getLoadingImage(self):
		return Gtk.Image.new_from_icon_name("image-loading-symbolic.symbolic", Gtk.IconSize.DIALOG)

	# GTK
	def getErrorImage(self):
		return Gtk.Image.new_from_icon_name("image-missing-symbolic.symbolic", Gtk.IconSize.DIALOG)

	def downloadToFile(self, url, toFile):
		response = requests.get(url)
		open(toFile, 'wb').write(response.content)

	def cropToSquare(self, pixbuf):
		height = pixbuf.get_height()
		width = pixbuf.get_width()
		smallerValue = height if height < width else width
		src_x = (width - smallerValue) // 2
		src_y = (height - smallerValue) // 2
		return pixbuf.new_subpixbuf(src_x, src_y, smallerValue, smallerValue)

	def loadImage(self, path, width, height):
		try:
			pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename=str(path), width=width, height=height)
		except GLib.Error:
			os.remove(path)
			return self.getErrorImage()

		buf_height = pixbuf.get_height()
		buf_width = pixbuf.get_width()
		if buf_width != buf_height:
			if buf_width > buf_height:
				pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename=str(path), width=-1, height=height)
			else:
				pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename=str(path), width=width, height=-1)
			pixbuf = self.cropToSquare(pixbuf)

		return pixbuf

	def getCoverPath(self, coverType, ID):
		possibleTypes = [ 'playlist', 'album' ]
		if coverType not in possibleTypes:
			coverType = 'ERRORTypeDoesNotExist'
		playlistCachePath = BaseDirectory.save_cache_path(Config.applicationID + 'coverArt' + coverType)
		playlistCachePath += ID
		return playlistCachePath

	def loadCoverFromCache(self, coverType, ID):
		cachePath = self.getCoverPath(coverType, ID)
		if os.path.isfile(cachePath):
			return self.loadImage(path=cachePath, width=self.imageSize, height=self.imageSize)
		return None

	def asyncUpdateCover(self, coverType, parent, updateMe, ID, url):

		# GTK
		def updateInParent(image):
			parent.remove(updateMe)
			parent.pack_start(image, False, True, 5)
			parent.show_all()

		def updateInParent_pixbuf(newChild):

			# GTK
			def toImage():
				updateInParent(Gtk.Image.new_from_pixbuf(newChild))
			GLib.idle_add(priority=GLib.PRIORITY_LOW, function=toImage)

		def tryReloadOrFail():
			newCover = self.loadCoverFromCache(coverType=coverType, ID=ID)
			if not newCover:
				# GTK
				def fail():
					updateInParent(self.getErrorImage())
				GLib.idle_add(priority=GLib.PRIORITY_LOW, function=fail)
			else:
				updateInParent_pixbuf(newCover)

		def updateCover():
			self.downloadToFile(url=url, toFile=self.getCoverPath(coverType, ID))
			tryReloadOrFail()

		def tryCacheFirst():
			newCover = self.loadCoverFromCache(coverType=coverType, ID=ID)
			if not newCover:
				updateCover()
			else:
				updateInParent_pixbuf(newCover)
		thread = threading.Thread(target=tryCacheFirst)
		thread.start()

	def asyncUpdatePlaylistCover(self, parent, updateMe, ID, url):
		self.asyncUpdateCover('playlist', parent, updateMe, ID, url)

	def asyncUpdateAlbumCover(self, parent, updateMe, ID, url):
		self.asyncUpdateCover('album', parent, updateMe, ID, url)
