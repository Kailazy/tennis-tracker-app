#!/usr/bin/env python3
# USAGE
# python webstreaming.py --ip 0.0.0.0 --port 8000

# import the necessary packages
from importlib import import_module
from imutils.video import VideoStream
from imutils.video import FPS
from flask import request
from flask import Response
from flask import Flask
from flask import render_template
from flask import make_response
from events import Events
import urllib.parse
import socket
import threading
import argparse
import datetime
import imutils
import time
import cv2
import json
import traceback
import os

# class objects
events_obj = None
detection_obj = None
detection_thread = None
motion_obj = None
sound_intro_obj = None
sound_chomp_obj = None

# initialize a flask object
app = Flask(__name__)
args = None
vs = None

@app.after_request
def add_header(response):
	response.cache_control.max_age = 0
	response.cache_control.no_cache = True
	return response

@app.route("/")
def index():
	# return the rendered template
	return render_template("index.html")

@app.route("/widget/voltage")
def voltage():
	# return the rendered template
	return render_template("voltage.html")

def generate():
	# grab global references to the output frame and lock variables
	global detection_obj

	# loop over frames from the output stream
	while detection_obj is not None:
		# wait until the lock is acquired
		with detection_obj.lock:
			# check if the output frame is available, otherwise skip
			# the iteration of the loop
			if detection_obj.outputFrame is None:
				#print("detection_obj.outputFrame is None")
				continue

			# encode the frame in JPEG format
			(flag, encodedImage) = cv2.imencode(".jpg", detection_obj.outputFrame)

			# ensure the frame was successfully encoded
			if not flag:
				#print("flag is False")
				continue

		# yield the output frame in the byte format
		yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
			bytearray(encodedImage) + b'\r\n')

@app.route("/video_feed")
def video_feed():
	# return the response generated along with the specific media
	# type (mime type)
	return Response(generate(), mimetype = "multipart/x-mixed-replace; boundary=frame")	

@app.route("/motion_reset", methods=["POST"])
def motion_reset():
	if (motion_obj):
		motion_obj.reset()
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_jiggle", methods=["POST"])
def motion_jiggle():
	if (motion_obj):
		motion_obj.left(100, 10)
		time.sleep(1)
		motion_obj.right(100, 10)
		time.sleep(1)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_stop", methods=["POST"])
def motion_stop():
	if (motion_obj):
		motion_obj.move(speed=0)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_left", methods=["POST"])
def motion_left():
	if (motion_obj):
		speed = request.args.get('speed', type = int)
		motion_obj.turn(speed=speed)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_right", methods=["POST"])
def motion_right():
	if (motion_obj):
		speed = request.args.get('speed', type = int)
		motion_obj.turn(speed=-speed)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_fwd", methods=["POST"])
def motion_fwd():
	if (motion_obj):
		speed = request.args.get('speed', type = int)
		motion_obj.move(speed=speed)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_back", methods=["POST"])
def motion_back():
	if (motion_obj):
		speed = request.args.get('speed', type = int)
		motion_obj.move(speed=-speed)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_joystick", methods=["POST"])
def motion_joystick():
	if (motion_obj):
		move_speed = request.args.get('move_speed', default=0, type = int)
		turn_speed = request.args.get('turn_speed', default=0, type = int)
		motion_obj.joystick(move_speed=move_speed, turn_speed=turn_speed)
		
		if sound_chomp_obj:
			if move_speed != 0:
				sound_chomp_obj.play()
			else:
				sound_chomp_obj.pause()

		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/motion_tracking", methods=["GET","POST"])
def motion_tracking():
	if (motion_obj):
		tracking = motion_obj.tracking("flip" if request.method == "POST" else None)
		return '{ "result": "SUCCESS" }'
	return '{}'

@app.route("/events", methods=["GET"])
def events():
	if (events_obj):
		format = urllib.parse.unquote(request.args.get('format', default='JSON', type = str))
		type = urllib.parse.unquote(request.args.get('type', default='%', type = str))
		time = urllib.parse.unquote(request.args.get('time', default='%', type = str))
		since = urllib.parse.unquote(request.args.get('since', default='', type = str))
		session = request.args.get('session', default=None, type = str)
		event = urllib.parse.unquote(request.args.get('event', default='%', type = str))
		limit = request.args.get('limit', default=100, type = int)
		flat = request.args.get('flat', default='', type = str)
		response = make_response(events_obj.get(format=format, type=type, time=time, since=since, session=session, event=event, limit=limit, flat=flat), 200)
		response.mimetype = "text/plain"
		return response
	return '{}'

@app.route("/sessions", methods=["GET"])
def sessions():
	if (events_obj):
		type = urllib.parse.unquote(request.args.get('type', default='%', type = str))
		response = make_response(events_obj.sessions(type), 200)
		response.mimetype = "text/plain"
		return response
	return '{}'

@app.route("/update", methods=["GET","POST"])
def update():
	if (request.method == "GET"):
		pass
	elif (request.method == "POST"):
		if vs:
			vs.stream.release()
			vs.stop()
		os.system(os.getcwd() + '/start -s LAST_SESSION')
	return '{}'

@app.route("/config", methods=["GET","POST"])
def config():
	if (motion_obj and detection_obj):
		if (request.method == "GET"):
			response = make_response(json.dumps({ 
				"detection.colorRange.lower": str(detection_obj.colorLower), 
				"detection.colorRange.upper": str(detection_obj.colorUpper), 
				"motion.speed": str(motion_obj.speed), 
				"motion.ramp": str(motion_obj.ramp),
				"session": events_obj.session,
			}, indent = 2), 200)
			response.mimetype = "text/plain"
			return response
		elif (request.method == "POST"):
			config = json.loads(request.data)
			if 'detection.colorRange.lower' in config.keys(): 
				detection_obj.colorLower = eval(config['detection.colorRange.lower'])
				print("Setting colorLower = " + str(detection_obj.colorLower))
			if 'detection.colorRange.upper' in config.keys(): 
				detection_obj.colorUpper = eval(config['detection.colorRange.upper'])
				print("Setting colorUpper = " + str(detection_obj.colorUpper))
			if 'motion.speed' in config.keys(): 
				motion_obj.speed = eval(config['motion.speed'])
				print("Setting speed = " + str(motion_obj.speed))
			if 'motion.ramp' in config.keys(): 
				motion_obj.ramp = eval(config['motion.ramp'])
				print("Setting ramp = " + str(motion_obj.ramp))
			return '{ "result": "SUCCESS" }'
	return '{}'

def get_ip():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		s.connect(("8.8.8.8", 80))
		ip = s.getsockname()[0]
		s.close()
	except:
		ip = "127.0.0.1"
	return ip

# check to see if this is the main thread of execution
if __name__ == '__main__':
	# construct the argument parser and parse command line arguments
	ap = argparse.ArgumentParser()
	ap.add_argument("-dc", "--detection-class", type=str, default="detection_ball.BallDetector",
		help="detection class to execute with the tracker (eg. -dc detection_ball.BallDetector")
	ap.add_argument("-mc", "--motion-class", type=str, default="motion_modbus.Move",
		help="motion class to execute with the tracker (eg. -mc motion_adeept.Move")
	ap.add_argument("-snd", "--sound-class", type=str, default="sound_pyaudio.Sound",
		help="sound class to execute with the tracker (eg. -mc sound_pyaudio.Sound")
	ap.add_argument("-i", "--ip", type=str, default=get_ip(),
		help="ip address of the device")
	ap.add_argument("-o", "--port", type=int, default=5000,
		help="ephemeral port number of the server (1024 to 65535)")
	ap.add_argument("-s", "--event-session", type=str,
		help="UUID for an existing session ID to join")
	ap.add_argument("-f", "--frame-count", type=int, default=32,
		help="# of frames used to construct the background model")
	ap.add_argument("-db", "--database-file", type=str, default="tracker.db",
		help="name of sqlite3 database file (eg. -db trackee.db")
	ap.add_argument("-vs", "--video-stream", type=int, default=0,
		help="VideStream source (eg. -vs 0). If -1 then no video stream.")
	args = vars(ap.parse_args())

	# initialize the video stream and allow the camera sensor to warmup
	try:
		if args["video_stream"] >= 0:
			#vs = VideoStream(usePiCamera=1).start()
			vs = VideoStream(src=args["video_stream"]).start()
			time.sleep(1.0)
		else:
			vs = None
	except:
		vs = None
		
	# initialize the event object
	events_obj = Events(args["database_file"], args['event_session'] if 'event_session' in args else None)

	# initialize the sound objects
	try:
		module_path, class_name = args["sound_class"].rsplit('.', 1)
		module = import_module(module_path)
		sound_intro_obj = getattr(module, class_name)("sounds/pacman_beginning.wav", loop_sound=False)
		sound_chomp_obj = getattr(module, class_name)("sounds/pacman_chomp.wav", loop_sound=True)
	except Exception as e:
		print("Couldn't find the sound class " + str(args) + str(e))

	# initialize the motion object
	try:
		module_path, class_name = args["motion_class"].rsplit('.', 1)
		module = import_module(module_path)
		motion_obj = getattr(module, class_name)(events_obj)
	except Exception as e:
		print("Couldn't find the motion class in the arguments: " + str(args) + str(e))
		traceback.print_exc()

	# initialize the detection object
	try:
		module_path, class_name = args["detection_class"].rsplit('.', 1)
		module = import_module(module_path)
		detection_obj = getattr(module, class_name)(events_obj, motion_obj, vs)
	except Exception as e:
		print("Couldn't find the detector class " + str(args) + str(e))

	# initialize the RPI object
	try:
		module_path, class_name = ["rpi", "RPI"]
		module = import_module(module_path)
		RPI_obj = getattr(module, class_name)(events_obj)
	except Exception as e:
		print("Couldn't find the RPI class " + str(args) + str(e))

	# start a thread that will perform the selected action
	if detection_obj != None:
		detection_thread = threading.Thread(target=detection_obj.thread, args=(args, None), name="ImageProcessingThread")
		detection_thread.daemon = True
		detection_thread.start()
		print('Detection Started')

		# play the startup sound
		if sound_intro_obj:
			sound_intro_obj.play()

		# start the flask app
		app.run(host=args["ip"], port=args["port"], debug=True, threaded=True, use_reloader=False)
	else:
		print('None detection obj')

# release the video stream pointer
vs.stop()
