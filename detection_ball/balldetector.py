# import the necessary packages
from collections import deque
import cv2
import imutils
import datetime
import time
import threading
import base64
import traceback
import numpy

class BallDetector:
	def __init__(self, events, motion, vs):
		# initialize the output frame and a lock used to ensure thread-safe
		# exchanges of the output frames (useful for multiple browsers/tabs
		# are viewing tthe stream)
		self.outputFrame = None
		self.lock = threading.Lock()
		
		# Related objects
		self.events = events
		self.motion = motion
		self.vs = vs
			
		# Color filters
		self.colorLower = (14, 86, 6)			   	#The color that openCV find
		self.colorUpper = (74, 255, 255)		  	#USE HSV value NOT RGB
		
		#colorLower = (24, 100, 100)			   	#The color that openCV find
		#colorUpper = (44, 255, 255)			   	#USE HSV value NOT RGB
		
		# from ORIGINAL
		#colorLower = (29, 86, 6)
		#colorUpper = (64, 255, 255)

		self.rotation_coeficient = 250

		self.error = None
		self.error_visible_until = None

	def thread(self, args, dummy):
		motion_stats = None

		print('Running')
		
		# loop over frames from the video stream
		while 42:
			try:
				font = cv2.FONT_HERSHEY_SIMPLEX
				
				# read the next frame from the video stream, resize it,
				try:
					frame = self.vs.read()
					frame = imutils.resize(frame, width=640)
				except:
					frame = numpy.zeros((480, 640, 3), numpy.uint8)
					cv2.putText(frame, "Missing Video Stream", (10, 400), font, 3, (255, 255, 255), 1)
				(screen_height, screen_width, channels) = frame.shape
				center_X = int(screen_width/2)
				center_Y = int(screen_height/2)

				# grab the current timestamp and draw it on the frame
				timestamp = datetime.datetime.now()
				cv2.putText(frame, timestamp.strftime("%A %d %B %Y %I:%M:%S%p") + " - captured %d events [%s]" % (self.events.captured_events, self.events.session), (10, frame.shape[0] - 10), font, 0.35, (255, 255, 255), 1)

				image = frame
				cv2.line(image,(center_X-20,center_Y),(center_X+20,center_Y),(128,255,128),1)
				cv2.line(image,(center_X,center_Y-20),(center_X,center_Y+20),(128,255,128),1)

				hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
				mask = cv2.inRange(hsv, self.colorLower, self.colorUpper)
				mask = cv2.erode(mask, None, iterations=2)
				mask = cv2.dilate(mask, None, iterations=2)
				cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
				center = None
				if len(cnts) > 0:
					#led.both_off()
					#led.green()
					cv2.putText(image,'Target Detected',(40,20), font, 0.5,(255,255,255),1,cv2.LINE_AA)
					c = max(cnts, key=cv2.contourArea)
					((x, y), radius) = cv2.minEnclosingCircle(c)
					M = cv2.moments(c)
					center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
					X = int(x)
					Y = int(y)
					if radius > 10:
						cv2.rectangle(image,(int(x-radius),int(y+radius)),(int(x+radius),int(y-radius)),(255,255,255),1)

						if int(x+radius) < center_X:
							mu1 = max(0, center_X - (x+radius))
							if (self.motion and self.motion.tracking() >= "ON"):
								self.left(mu1, radius)
								str = 'Moving LEFT'
							else:
								str = 'Tracking LEFT'
							cv2.putText(image,'Radius=%d, Pixels from center=%d, %s' % (mu1, radius, str),
										(40,60), font, 
										0.5,(255,255,255),1,cv2.LINE_AA)
						elif int(x-radius) > center_X:
							mu1 = max(0, (x-radius) - center_X)
							if (self.motion and self.motion.tracking() >= "ON"):
								self.right(mu1, radius)
								str = 'Moving REGHT'
							else:
								str = 'Tracking RIGHT'
							cv2.putText(image,'Radius=%d,  Pixels from center=%d, %s' % (mu1, radius, str),
										(40,60), font, 
										0.5,(255,255,255),1,cv2.LINE_AA)

						if radius > 22:
							if (self.motion and self.motion.tracking() >= "ON with MOVE"):
								self.move(-0.2)
							cv2.putText(image,'Too Close',(40,40), font, 0.5,(128,128,255),1,cv2.LINE_AA)
						elif radius < 18:
							if (self.motion and self.motion.tracking() >= "ON with MOVE"):
								self.move(0.2)
							cv2.putText(image,'Object Tracking',(40,40), font, 0.5,(128,255,128),1,cv2.LINE_AA)
						else:
							cv2.putText(image,'In Position',(40,40), font, 0.5,(255,128,128),1,cv2.LINE_AA)
		
						if X > center_X-40 and X < center_X+40:
							#print('looked')
							cv2.line(image,(center_X-20,center_Y),(center_X+20,center_Y),(64,64,255),1)
							cv2.line(image,(center_X,center_Y-20),(center_X,center_Y+20),(64,64,255),1)
							cv2.rectangle(image,(int(x-radius),int(y+radius)),
								(int(x+radius),int(y-radius)),(64,64,255),1)
				else:
					cv2.putText(image,'Target Detecting',(40,20), font, 0.5,(255,255,255),1,cv2.LINE_AA)

				# Show motion tracking state and voltage
				self.darken_region(image, (screen_width-40-100 - 10, 5), (200, 45), 0.75)
				if self.motion:
					text = "Tracking: " + self.motion.tracking()
					cv2.putText(image,text,(screen_width-40-100,20), font, 0.5,(255,255,255),1,cv2.LINE_AA)

					voltage_stats = self.motion.get_voltage_stats() if self.motion else None
					if voltage_stats:
						text = "Voltage: "
						if "error" in voltage_stats:
							text += voltage_stats["error"]
						else:
							text += "%.2f" % voltage_stats['voltage']
						for i, line in enumerate(text.split('\n')):
							cv2.putText(image, line, (screen_width-40-100, 40), font, (.5), (255,255,255), 1, cv2.LINE_AA)

				# Show motion stats
				motion_stats = self.motion.get_motion_stats() if self.motion else None
				if motion_stats:
					# Show if there is an error
					if not 'devices' in motion_stats or 'error' in motion_stats:
						self.darken_region(image, (20, screen_height-40-20), (400, 40), 0.75)
						error = ""
						if "error" in motion_stats:
							error += "Motion Stats: " + motion_stats["error"] + "\n"
						else:
							error = "ERROR: No communicatoin with motion devices"
						for i, line in enumerate(error.split('\n')):
							cv2.putText(image, line, (20, screen_height-40-30+i*20), font, (0.5), (255,255,255), 1, cv2.LINE_AA)
				
					# Otherwise show the motor and voltage stats
					else:
						# Show Motor 1 Stats
						self.darken_region(image, (20, screen_height-40-90-20), (200, 120), 0.75)
						motor1 = list(filter(lambda device: device and "id" in device and device["id"] == "motor1", motion_stats["devices"]))
						text = "Left Motor (1)\n"
						if len(motor1) == 0:
							text += "ERROR: couldn't find stat.devices[].id=motor1"
						elif 'error' in motor1[0]:
							text += "ERROR: " + motor1[0]['error']
						else:
							text += "PositionRef: %.2f\n" % motor1[0]['position_ref'] +\
									"Position: %.2f\n" % motor1[0]['current_position'] +\
									"SpeedRef: %.2f RPM\n" % motor1[0]['requested_speed'] +\
									"Speed: %.2f RPM\n" % motor1[0]['current_speed']
						for i, line in enumerate(text.split('\n')):
							cv2.putText(image, line, (30, screen_height-40-80+i*20 - 5 * (i==0)), font, (0.75 if i == 0 else .5), (255,255,255), 1, cv2.LINE_AA)

						# Show Motor 2 Stats
						self.darken_region(image, (220, screen_height-40-90-20), (200, 120), 0.75)
						motor2 = list(filter(lambda device: device and "id" in device and device["id"] == "motor2", motion_stats["devices"]))
						text = "Right Motor (2)\n"
						if len(motor2) == 0:
							text += "ERROR: couldn't find stat.devices[].id=motor2"
						elif 'error' in motor2[0]:
							text += "ERROR: " + motor2[0]['error']
						else:
							text += "PositionRef: %.2f\n" % motor2[0]['position_ref'] +\
									"Position: %.2f\n" % motor2[0]['current_position'] +\
									"SpeedRef: %.2f RPM\n" % motor2[0]['requested_speed'] +\
									"Speed: %.2f RPM\n" % motor2[0]['current_speed']
						for i, line in enumerate(text.split('\n')):
							cv2.putText(image, line, (230, screen_height-40-80+i*20 - 5 * (i==0)), font, (0.75 if i == 0 else .5), (255,255,255), 1, cv2.LINE_AA)

				# Print the filter
				mask = imutils.resize(mask, width=190)
				self.overlay_image_alpha(image, mask, (screen_width - 210, screen_height - 160))
						
				# acquire the lock, set the output frame, and release the
				# lock
				with self.lock:
					self.outputFrame = image.copy()

			except Exception as e:
				traceback.print_exc()

	def overlay_image_alpha(self, img, img_overlay, pos, alpha_mask=None):
		"""Overlay img_overlay on top of img at the position specified by
		pos and blend using alpha_mask.

		Alpha mask must contain values within the range [0, 1] and be the
		same size as img_overlay.
		"""

		try:
			x, y = pos

			# Image ranges
			y1, y2 = max(0, y), min(img.shape[0], y + img_overlay.shape[0])
			x1, x2 = max(0, x), min(img.shape[1], x + img_overlay.shape[1])

			# Overlay ranges
			y1o, y2o = max(0, -y), min(img_overlay.shape[0], img.shape[0] - y)
			x1o, x2o = max(0, -x), min(img_overlay.shape[1], img.shape[1] - x)

			# Exit if nothing to do
			if y1 >= y2 or x1 >= x2 or y1o >= y2o or x1o >= x2o:
				return

			channels = img.shape[2]

			alpha = alpha_mask[y1o:y2o, x1o:x2o] if alpha_mask != None else 1.0
			alpha_inv = 1.0 - alpha

			for c in range(channels):
				a = alpha * img_overlay[y1o:y2o, x1o:x2o]
				b = alpha_inv * img[y1:y2, x1:x2, c]
				img[y1:y2, x1:x2, c] = (a + b)
		except:
			pass

	def darken_region(self, img, pos, size, alpha):
		"""Darkenr imgage at the position specified by
		pos and blend using alpha.

		Alpha mask must contain values within the range [0, 1] and be the
		same size as img_overlay.
		"""

		try:
			x, y = pos
			w, h = size

			# Image ranges
			y1, y2 = max(0, y), min(img.shape[0], y + h)
			x1, x2 = max(0, x), min(img.shape[1], x + w)

			# Overlay ranges
			y1o, y2o = max(0, -y), min(h, img.shape[0] - y)
			x1o, x2o = max(0, -x), min(w, img.shape[1] - x)

			# Exit if nothing to do
			if y1 >= y2 or x1 >= x2 or y1o >= y2o or x1o >= x2o or alpha == None:
				return

			channels = img.shape[2]

			for c in range(channels):
				a = alpha * img[y1:y2, x1:x2, c]
				img[y1:y2, x1:x2, c] = a
		except:
			pass

	def right(self, pixels, radius):
		self.motion.turn(pixels*radius/self.rotation_coeficient)

	def left(self, pixels, radius):
		self.motion.turn(-pixels*radius/self.rotation_coeficient)

	def move(self, meters):
		self.motion.move(meters)
