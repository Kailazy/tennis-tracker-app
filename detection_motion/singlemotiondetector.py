# import the necessary packages
import numpy as np
import imutils
import cv2
import datetime
import time
import threading

class SingleMotionDetector:
	def __init__(self, accumWeight=0.5):
		# store the accumulated weight factor
		self.accumWeight = accumWeight

		# initialize the background model
		self.bg = None

		# initialize the output frame and a lock used to ensure thread-safe
		# exchanges of the output frames (useful for multiple browsers/tabs
		# are viewing tthe stream)
		self.outputFrame = None
		self.lock = threading.Lock()

	def update(self, image):
		# if the background model is None, initialize it
		if self.bg is None:
			self.bg = image.copy().astype("float")
			return

		# update the background model by accumulating the weighted
		# average
		cv2.accumulateWeighted(image, self.bg, self.accumWeight)

	def detect(self, image, tVal=25):
		# compute the absolute difference between the background model
		# and the image passed in, then threshold the delta image
		delta = cv2.absdiff(self.bg.astype("uint8"), image)
		thresh = cv2.threshold(delta, tVal, 255, cv2.THRESH_BINARY)[1]

		# perform a series of erosions and dilations to remove small
		# blobs
		thresh = cv2.erode(thresh, None, iterations=2)
		thresh = cv2.dilate(thresh, None, iterations=2)

		# find contours in the thresholded image and initialize the
		# minimum and maximum bounding box regions for motion
		cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE)
		cnts = imutils.grab_contours(cnts)
		(minX, minY) = (np.inf, np.inf)
		(maxX, maxY) = (-np.inf, -np.inf)

		# if no contours were found, return None
		if len(cnts) == 0:
			return None

		# otherwise, loop over the contours
		for c in cnts:
			# compute the bounding box of the contour and use it to
			# update the minimum and maximum bounding box regions
			(x, y, w, h) = cv2.boundingRect(c)
			(minX, minY) = (min(minX, x), min(minY, y))
			(maxX, maxY) = (max(maxX, x + w), max(maxY, y + h))

		# otherwise, return a tuple of the thresholded image along
		# with bounding box
		return (thresh, (minX, minY, maxX, maxY))

	def thread(self, vs, args):
		# grab global references to the video stream, output frame, and
		# lock variables
		#global vs, outputFrame, lock

		# initialize the motion detector and the total number of frames
		# read thus far
		#md = SingleMotionDetector(accumWeight=0.1)
		total = 0
		try:
			frameCount = args["frame_count"]
		except:
			frameCount = 32

		# loop over frames from the video stream
		while True:
			# read the next frame from the video stream, resize it,
			# convert the frame to grayscale, and blur it
			frame = vs.read()
			frame = imutils.resize(frame, width=400)
			gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
			gray = cv2.GaussianBlur(gray, (7, 7), 0)

			# grab the current timestamp and draw it on the frame
			timestamp = datetime.datetime.now()
			cv2.putText(frame, timestamp.strftime(
				"%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10),
				cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

			# if the total number of frames has reached a sufficient
			# number to construct a reasonable background model, then
			# continue to process the frame
			if total > frameCount:
				# detect motion in the image
				motion = self.detect(gray)

				# cehck to see if motion was found in the frame
				if motion is not None:
					# unpack the tuple and draw the box surrounding the
					# "motion area" on the output frame
					(thresh, (minX, minY, maxX, maxY)) = motion
					cv2.rectangle(frame, (minX, minY), (maxX, maxY),
						(0, 0, 255), 2)
			
			# update the background model and increment the total number
			# of frames read thus far
			self.update(gray)
			total += 1

			# acquire the lock, set the output frame, and release the
			# lock
			with self.lock:
				self.outputFrame = frame.copy()

			# going to refactor this project at some point soon !

