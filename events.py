#!/usr/bin/env python3
import time
import datetime
import threading
import traceback
import os
import sqlite3
import json
import uuid
from deepdiff import DeepDiff

class Events:

	def __init__(self, file_name, continue_existing_session=None):
		self.db_file_name = file_name
		if continue_existing_session == "LAST_SESSION":
			self.session = self.get_last_session()
		elif continue_existing_session != None:
			self.session = continue_existing_session
		else:
			self.session = uuid.uuid4().hex[:16]

		self.lock = threading.Lock()
		self.events = []
		self.captured_events = 0
		self.len_after_which_to_flush_events_to_db = 10

		# connect to the database (will create it if not existing)
		connection = sqlite3.connect(self.db_file_name)

		# create the table if it doesn't exist yet
		connection.execute('''CREATE TABLE IF NOT EXISTS events (
							type text NOT NULL,
							time text NOT NULL,
							session text NOT NULL,
							event text
						);''')
		
		# close the connection
		connection.close()

	def post(self, event):
		with self.lock:

			# promote interesting event attributes as first class attributes
			# from [{}, ...] to [(type, time, {}), ...]
			event = event if type(event) is list else [event]
			event = list(map(lambda e: {
				"type": e['type'] if e and 'type' in e else 'UNKNOWN', 
				"time": e['time'] if e and 'time' in e else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
				"session": self.session,
				"event": str(e)
			}, event))
					
			# store the event
			self.events.extend(event)
			self.captured_events += len(event)

			# if we've reached the max of the in memory buffer - write to DB
			if len(self.events) >= self.len_after_which_to_flush_events_to_db:
				self.flush_to_db()

	def flush_to_db(self):
		try:
			# example:
			#rows = [('2006-03-28', 'BUY', 'IBM', 1000, 45.00),
			#		('2006-04-05', 'BUY', 'MSOFT', 1000, 72.00),
			#		('2006-04-06', 'SELL', 'IBM', 500, 53.00)]
			#c.execute

			# move events to a flush events and clear events
			flush_events = self.events
			self.events = []

			# connect to the database (will create it if not existing)
			connection = sqlite3.connect(self.db_file_name)

			# SQL-ize the event objects
			events = list(map(lambda event: (event['type'], event['time'], event['session'], str(event['event'])), flush_events))

			# insert the events
			connection.executemany('insert into events(type, time, session, event) values (?,?,?,?)', events)

			# commit all changes
			connection.commit()	
		finally:
			connection.close()

	def schedule(self, schedule_obj):

		# generate the event
		event = schedule_obj['generation_function']()

		# check if we should post the event - this is trick while to make sure it runs only once
		for i in [42]:
			# break if ignoring a None event
			if  event == None and 'ignore_none' in schedule_obj and schedule_obj['ignore_none']: break

			# in any case set the last event in the same schedule even if it hasn't been posted
			schedule_obj['last_event'] = event

			# break if ignoring an event that is the same as the last event in the same schedule
			if 'ignore_same' in schedule_obj and schedule_obj['ignore_same'] and \
				DeepDiff(schedule_obj['last_event'] if 'last_event' in schedule_obj else None, \
						event, \
						exclude_paths=schedule_obj['ignore_paths'] if 'ignore_paths' in schedule_obj else None) == {}: break

			# if the scheduler wants to include context around a condition and otherwise filter out events
			if 'active_listening' in schedule_obj:
				# make sure to initialize the before_events queue if not yet
				if not 'before_events' in schedule_obj: schedule_obj['before_events'] = [] 

				# get the active listenting details from the scheduler and run the active function
				before, activeFn = schedule_obj['active_listening']
				try:
				 	active = activeFn(event)
				except:
					active = False
				
				# if the current event is active then post all <before> events to the queue first and then the current active event
				if active:
					# mark the very first before_events event as series_start and post them all to the queue and clear them
					if schedule_obj['before_events'] and schedule_obj['before_events'][0]: 
						schedule_obj['before_events'][0]['series_start'] = True
					self.post(schedule_obj['before_events'])
					schedule_obj['before_events'] = []

					# also post the current аctive event to the queue
					self.post(event)

				# if the current event is not active then append only to the before_events and prune them to <before>
				else:
					schedule_obj['before_events'].append(event)

					# prune the older than <before> events
					since = (datetime.datetime.now() - datetime.timedelta(milliseconds=before)).strftime('%Y-%m-%d %H:%M:%S.%f')
					schedule_obj['before_events'] = list(filter(lambda e: e['time'] >= since, schedule_obj['before_events']))

			else:
				# post the event to the queue
				self.post(event)

		# schedule the next recurring schedule
		schedule_obj['last_thread'] = threading.Timer(schedule_obj['every_x_seconds'], self.schedule, args=[schedule_obj])
		schedule_obj['last_thread']._name = schedule_obj['name'] if 'name' in schedule_obj else "UnknownEventTimerThread"
		schedule_obj['last_thread'].start()

		return schedule_obj

	def get_last_session(self):

		# connect to the database (will create it if not existing)
		connection = sqlite3.connect(self.db_file_name)

		# query the table if it doesn't exist yet
		results = connection.execute('''SELECT session 
										FROM events
										ORDER BY time DESC 
										LIMIT 1;''').fetchall()

		# close connection
		connection.close()

		return results[0][0]
						
	def get(self, format="JSON", type='%', time='%', since='%', session=None, event='%', limit=100, flat=''):	# CSV will have flat=True by default
		# first flush to DB
		self.flush_to_db()

		# change to only this session if empty string
		session = self.session if session == None else session

		# connect to the database (will create it if not existing)
		connection = sqlite3.connect(self.db_file_name)

		# query the table if it doesn't exist yet
		results = connection.execute('''SELECT event 
										FROM events 
										WHERE type LIKE ?
										  AND time LIKE ?
										  AND time > ?
										  AND session LIKE ?
										  AND event LIKE ?
										ORDER BY time DESC 
										LIMIT ?;''', [
											type,
											time,
											since,
											session,
											event,
											str(limit)
										]).fetchall()


		# close connection
		connection.close()

		# Get the list of stats
		def JSON2DICT(x):  
			try:
				return json.loads(x[0].replace("'", "\""))
			except:
				return {}
		results = list(map(JSON2DICT, results))

		def flatten(d, sep="_"):
			import collections
			obj = collections.OrderedDict()
			def recurse(t,parent_key=""):
				if isinstance(t,list):
					for i in range(len(t)):
						recurse(t[i],parent_key + sep + str(i) if parent_key else str(i))
				elif isinstance(t,dict):
					for k,v in t.items():
						recurse(v,parent_key + sep + k if parent_key else k)
				else:
					obj[parent_key] = t
			recurse(d)
			return obj


		if format == "JSON":
			try:
				if flat:
					results = list(map(flatten, results))
				return json.dumps(results, indent=2)
			except:
				return str(results)

		elif format == "CSV":				
			try:
				# CSV files are always flat
				rows = list(map(flatten, results))
				if len(rows) > 0:
					return ",".join(rows[0].keys()) + "\n" + "\n".join(map(lambda row: ",".join(map(lambda x: str(x), row.values())), rows))
				else:
					return ""	
			except:
				return str(results)

		else:
			return "UNKNOWN FORMAT: %s - try JSON or CSV (all caps)" % format

	def sessions(self, type='%'):

				# first flush to DB
		self.flush_to_db()

		# connect to the database (will create it if not existing)
		connection = sqlite3.connect(self.db_file_name)

		# query the table if it doesn't exist yet
		results = connection.execute('''SELECT DISTINCT session, min(time) as 'from', max(time) as 'to', count(*) as 'count' 
										FROM events 
										WHERE type LIKE ?
										GROUP BY session 
										ORDER BY 'from' DESC;''', [
											type
										]).fetchall()

		# close connection
		connection.close()

		return str(list(map(lambda x: { "session": x[0], "from": x[1], "to": x[2], "count": x[3], "current": x[0] == self.session }, results))) \
			.replace("'", "\"") \
			.replace(": True", ": true") \
			.replace(": False", ": false")
