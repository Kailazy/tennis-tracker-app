import os
import wave
import threading
import sys
import pyaudio
import time

class Sound(threading.Thread) :
	"""
	A simple class based on PyAudio to play wave loop.
	It's a threading class. You can play audio while your application
	continues to do its stuff. :)
	"""

	CHUNK = 1024

	def __init__(self,filepath,loop_sound=True,auto_start=True) :
		"""
		Initialize `WavePlayerLoop` class.
		PARAM:
			-- filepath (String) : File Path to wave file.
			-- loop (boolean)    : True if you want loop playback. 
									False otherwise.
		"""
		super(Sound, self).__init__()
		self.filepath = os.path.abspath(filepath)
		self.loop_sound = loop_sound
		self.running = True
		self.playing = False
		if auto_start:
			self.start()

	def run(self):
		# Open Wave File and start play!
		print("*** opening sound file")
		wf = wave.open(self.filepath, 'rb')
		print("*** opening sound player")
		player = pyaudio.PyAudio()
		stream = None

		# Open Output Stream (basen on PyAudio tutorial)
		attempts = 3
		while attempts:
			try:
				print("*** starting the sound stream")
				stream = player.open(format = player.get_format_from_width(wf.getsampwidth()), \
					channels = wf.getnchannels(), \
					rate = wf.getframerate(), \
					output = True)
				break
			except:
				attempts -= 1
				print("*** attempt %d failed to start the sound stream" % (3-attempts))

		# PLAYBACK LOOP
		if attempts > 0:
			print("*** starting the sound loop")
			while self.running:
				if self.playing:
					data = wf.readframes(self.CHUNK)
					if data == b'' : # If file is over then rewind.
						wf.rewind()
						self.playing = self.loop_sound
						continue
					stream.write(data)
				else:
					time.sleep(0.1)
		else:
			print("*** cannot start the sound stream - exiting the thread")

		if stream: stream.close()
		player.terminate()

	def play(self, rewind=False) :
		"""
		Just another name for self.start()
		"""
		if rewind: 
			wf.rewind()
		self.playing = True

	def pause(self) :
		"""
		Pause playback. 
		"""
		self.playing = False

	def kill(self) :
		"""
		Stop playback. 
		"""
		self.running = False