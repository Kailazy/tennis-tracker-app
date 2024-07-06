#!/usr/bin/env python3
import time
import datetime
import threading
import traceback
import getkey
import os

# accumulators
lock = threading.Lock()

class RPI:

	def __init__(self, events):
		# event queue
		self.events = events

		# schedule voltage stats events every 1 minute
		self.RPI_stats_schedule = self.events.schedule({
			'name': "RPIStatsTimerThread",
			'generation_function': self.generate_RPI_stats_event,
			'every_x_seconds': 1,										# every 1 minute
			'ignore_none': True,
			'ignore_same': False,
			'ignore_paths': ["root['time']"],
		})

	########################################## STATS EVENTS ##############################################################

	def generate_RPI_stats_event(self):
		global lock

		# event basics
		event = {
			'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
			'type': "RPI_stats"
		}

		with lock:
			RPIstats = []
			error = ""
			try:
				event['CPU_temperature'] = os.popen("vcgencmd measure_temp | awk -F \"[=\']\" '{printf(\"%0.2f\",$2)}'").read()
				RPIstats.append(event['CPU_temperature'])
			except Exception as e:
				error += "RPI Error: " + str(e) + "\n"
			
			try:
				event['CPU_load_percentage'] = os.popen("top -n1 | grep Cpu | awk '{printf(\"%0.2f\",$2)}'").read()
				RPIstats.append(event['CPU_load_percentage'])
			except Exception as e:
				error += "RPI Error: " + str(e) + "\n"
			
			try:
				event['MEM_usage_percentage'] = os.popen("free | grep Mem | awk '{printf(\"%0.2f\",$3/$2 * 100)}'").read()
				RPIstats.append(event['MEM_usage_percentage'])
			except Exception as e:
				error += "RPI Error: " + str(e) + "\n"

			if len(RPIstats) == 0:
				event['error'] = error

		return event

	def get_RPI_stats(self):
		return self.voltage_stats_schedule['last_event']

