#!/usr/bin/env python3
import minimalmodbus
import time
import datetime
import threading
import traceback
import getkey
import os

# accumulators
degrees_per_meter = 2160 					# default wheel ratio in rotation degrees per meter
degrees_per_degree = 6.3 					# default distance between ... in degrees per meter
lock = threading.Lock()
instruments = None
movement_completed_since = 0

MODBUS_REQUESTED_POSITION = 0        # 32 bit
MODBUS_REQUESTED_DURATION = 2
MODBUS_VOLTAGE = 3
MODBUS_POSITION = 4        			# 32 bit
MODBUS_AVG_SPEED = 6
MODBUS_REQUESTED_SPEED = 7
MODBUS_DEFAULT_CONTROL_MODE = 8
MODBUS_SPEED = 9
MODBUS_TORQUE_REF = 10
MODBUS_DEFAULT_TORQUE_REF = 11
MODBUS_DEFAULT_ID_REF = 12
MODBUS_CURRENT_AMPLITUDE = 13
MODBUS_VOLTAGE_AMPLITUDE = 14
MODBUS_FOC_IA = 15
MODBUS_FOC_IB = 16
MODBUS_FOC_ALPHA = 17
MODBUS_FOC_BETA = 18
MODBUS_FOC_IQ = 19
MODBUS_FOC_ID = 20
MODBUS_FOC_IQREF = 21
MODBUS_FOC_IDREF = 22
MODBUS_FOC_VIQ = 23
MODBUS_FOC_VID = 24
MODBUS_FOC_VALPHA = 25
MODBUS_FOC_VBETA = 26
MODBUS_FOC_EL_ANGLE_DPP = 27
MODBUS_FOC_TEREF = 28
MODBUS_EMPTY = 29
MODBUS_POSITION_REF = 30			# 32 bit

class Move:

	def __init__(self, events):
		self.speed = 50
		self.ramp = 1000

		# event queue
		self.events = events

		## Example: move 1 meter forward in 3000 ms
		self.setup(4, 0.2, 0.42, 500)		# reducer ratio of 6, 200mm wheels radius, 420mm base, 500ms per meter speed
		self.reset()

		# schedule motion stats events every 100ms
		self.motion_stats_schedule = self.events.schedule({
			'name': "MotionStatsTimerThread",
			'generation_function': self.generate_motion_stats_event,
			'every_x_seconds': 0.1,										# every 100ms
			'ignore_none': True,
			'ignore_same': False,
			'active_listening': (3000, lambda e: not self.movement_completed_for(3000)),
			'ignore_paths': ["root['time']"],							# exclude 
		})

		# schedule voltage stats events every 1 minute
		self.voltage_stats_schedule = self.events.schedule({
			'name': "VoltageStatsTimerThread",
			'generation_function': self.generate_voltage_stats_event,
			'every_x_seconds': 60,										# every 1 minute
			'ignore_none': True,
			'ignore_same': False,
			'ignore_paths': ["root['time']"],
		})

		# tracking
		self.tracking_mode = "OFF"

	# setup wheel radius and distance between wheels in meters
	def setup(self, reducer_ratio, wheels_radius, wheels_base, milliseconds_per_meter):
		global degrees_per_degree, degrees_per_meter

		if reducer_ratio > 0 and wheels_radius > 0 and wheels_base > 0:
			degrees_per_meter = (reducer_ratio * 360) / (2 * 3.1415926 * wheels_radius)
			degrees_per_degree = reducer_ratio * wheels_base / (2 * wheels_radius)

	######################################## PUBLIC MOTION COMMANDS ################################################################

	# reset
	def reset(self):
		global instruments

		try:
			# re-initialize the instruments
			command = os.popen('ls /dev/tty* | grep -i usb')
			usbport = command.read().split("\n")[0]
			instruments = [minimalmodbus.Instrument(usbport, 0), #, close_port_after_each_call=True), 
					minimalmodbus.Instrument(usbport, 1), #, close_port_after_each_call=True), 
					minimalmodbus.Instrument(usbport, 2)] #, close_port_after_each_call=True)]

			#i1 = minimalmodbus.Instrument('/dev/ttyUSB0', 1, close_port_after_each_call=True)						// Raspberry
			#i2 = minimalmodbus.Instrument('/dev/ttyUSB0', 2, close_port_after_each_call=True)						// Raspberry
			#i1 = minimalmodbus.Instrument('/dev/tty.usbserial-1410', 1, close_port_after_each_call=True)			// MacOS
			#i2 = minimalmodbus.Instrument('/dev/tty.usbserial-1410', 2, close_port_after_each_call=True)			// MacOS

			# reset both instruments
			self.reset_motor(0)
			#self.reset_motor(1)
			#self.reset_motor(2)
			time.sleep(2)
			result = "Reset complete"

		except Exception as e:
			instruments = None
			result = "ERROR: Cannot reset the controller: " + repr(e)

		# post the reset event
		if self.events: 
			event = {
				'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
				'type': 'motion_reset',
				'result': result
			}
			self.events.post(event)
			print(result)

	# joystick move
	def joystick(self, move_speed=0, turn_speed=0):
		self.setup_drive_command(1, -move_speed + turn_speed)
		self.setup_drive_command(2, move_speed + turn_speed)
		result = self.execute_drive_command()

		# post the joystick motion event
		self.post_motion_event('joystick', {
			'motor1_speed': -move_speed + turn_speed,
			'motor2_speed': move_speed + turn_speed,
			'result': result
		})

	# move [meters] meters with [speed] speed
	def move(self, speed=0, meters=0):

		# trigger the motors
		try:
			self.setup_drive_command(1, - speed)
			self.setup_drive_command(2, speed)
			result = self.execute_drive_command()
		except:
			traceback.print_exc()

		# post the motion event
		self.post_motion_event('drive', {
			'motor1_speed': -speed,
			'motor2_speed': speed,
			'result': result
		})

	# turn clockwise [degrees] degrees with [speed] speed
	def turn(self, speed=0, degrees=0):

		# trigger the motors
		try:
			self.setup_drive_command(1, speed)
			self.setup_drive_command(2, speed)
			result = self.execute_drive_command()
		except:
			traceback.print_exc()

		# post the motion event
		self.post_motion_event('drive', {
			'motor1_speed': speed,
			'motor2_speed': speed,
			'result': result
		})

	# tracking
	def tracking(self, command=None):
		if command == "flip":
			if self.tracking_mode == "OFF": self.tracking_mode = "ON"
			elif self.tracking_mode == "ON": self.tracking_mode = "ON with MOVE"
			else: self.tracking_mode = "OFF"

		return self.tracking_mode

	################################################ LOW LEVEL COMMANDS ########################################################

	def post_motion_event(self, command, details):
		# post the joystick motion event
		if self.events: 
			event = {
				'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
				'type': 'motion_command',
				'command': command,
			}
			event.update(details)
			self.events.post(event)

	# speed is in RPM
	def set_move_command(self, id, degree, speed = 250):
		global instruments, lock

		if instruments == None:
			print("ERROR: Instruments not initialized. Must call reset() first.")
			return "FAILURE"

		with lock:
			instr = instruments[id]
			degree = int(degree)
			angle = instr.read_long(MODBUS_POSITION, signed=True)
			if not speed > 250: speed = 250
			ms = int(abs(angle-degree) * 250 / speed)
			instr.write_long(MODBUS_REQUESTED_POSITION, degree, signed=True)
			instr.write_register(MODBUS_REQUESTED_DURATION, ms)
			instr.write_bit(5, 1)
			instr.write_bit(0, 1)

		return "SUCCESS"

	def execute_move_command(self):
		global instruments, lock

		if instruments == None:
			print("ERROR: Instruments not initialized. Must call reset() first.")
			return "FAILURE"

		with lock:
			instruments[0].write_bit(0, 1)

		return "SUCCESS"

	# speed is in RPM
	def setup_drive_command(self, id, speed):
		global instruments, lock

		if instruments == None:
			print("ERROR: Instruments not initialized. Must call reset() first.")
			return "FAILURE"

		with lock:
			instr = instruments[id]
			instr.write_register(MODBUS_REQUESTED_SPEED, int(speed), signed=True)
			instr.write_register(MODBUS_DEFAULT_CONTROL_MODE, 1, signed=True)
			#instr.write_bit(2, 1)

		return "SUCCESS"

	def execute_drive_command(self):
		global instruments, lock

		if instruments == None:
			print("ERROR: Instruments not initialized. Must call reset() first.")
			return "FAILURE"

		with lock:
			instruments[1].write_bit(5, 1)
			instruments[1].write_bit(2, 1)
			instruments[2].write_bit(5, 1)
			instruments[2].write_bit(2, 1)

		return "SUCCESS"

	def get_angle(self, id):
		global instruments, lock

		with lock:
			instr = instruments[id]
			return instr.read_long(MODBUS_POSITION, signed=True)

	def movement_completed_for(self, ms=0):
		global instruments, lock, movement_completed_since

		# If there are no instruments - return True to minimize the logging
		#if instruments == None:
		#	return True

		with lock:
			if instruments[1].read_bit(0) > 0 and instruments[2].read_bit(0) > 0:
				if movement_completed_since:
					return movement_completed_since + datetime.timedelta(milliseconds=ms) <= datetime.datetime.now() 
				else:
					movement_completed_since = datetime.datetime.now()
					return False
			else:
				movement_completed_since = 0
				return False			

	def reset_motor(self, id):
		global instruments, lock

		with lock:
			try:
				instr = instruments[id]
				#instr.write_bit(6, 1)
				instr.write_bit(7, 1)
				#time.sleep(1)
			except:
				#traceback.print_exc()
				pass
 
	########################################## STATS EVENTS ##############################################################

	def generate_motion_stats_event(self):
		global instruments, lock

		# event basics
		event = {
			'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
			'type': "motion_stats"
		}

		def read_signed_int(registers, address):
			unsigned_int = registers[address]
			bitsize = 16
			return unsigned_int if unsigned_int < (1 << bitsize-1) else unsigned_int - (1 << bitsize)

		def read_signed_long(registers, address):
			unsigned_long = (registers[address] << 16) + registers[address+1]
			bitsize = 32
			return unsigned_long if unsigned_long < (1 << bitsize-1) else unsigned_long - (1 << bitsize)

		def read_all_registers(id, name):
			try:
				start = time.time()
				registers = instruments[id].read_registers(0, 32)
				return {
					'id': name,
					'requested_speed': read_signed_int(registers, MODBUS_REQUESTED_SPEED),
					'current_speed': read_signed_int(registers, MODBUS_AVG_SPEED),
					'mecanical_speed': read_signed_int(registers, MODBUS_SPEED),
					'requested_position': read_signed_long(registers, MODBUS_REQUESTED_POSITION),
					'position_ref': read_signed_long(registers, MODBUS_POSITION_REF),
					'current_position': read_signed_long(registers, MODBUS_POSITION),
					'position_error': read_signed_long(registers, MODBUS_POSITION_REF) - read_signed_long(registers, MODBUS_POSITION),
					'torque_ref': read_signed_int(registers, MODBUS_TORQUE_REF),
					'default_torque_ref': read_signed_int(registers, MODBUS_DEFAULT_TORQUE_REF),
					'default_id_ref': read_signed_int(registers, MODBUS_DEFAULT_ID_REF),
					'current_amplitude': read_signed_int(registers, MODBUS_CURRENT_AMPLITUDE),
					'voltage_amplitude': read_signed_int(registers, MODBUS_VOLTAGE_AMPLITUDE),
					'foc_ia': read_signed_int(registers, MODBUS_FOC_IA),
					'foc_ib': read_signed_int(registers, MODBUS_FOC_IB),
					'foc_alpha': read_signed_int(registers, MODBUS_FOC_ALPHA),
					'foc_beta': read_signed_int(registers, MODBUS_FOC_BETA),
					'foc_iq': read_signed_int(registers, MODBUS_FOC_IQ),
					'foc_id': read_signed_int(registers, MODBUS_FOC_ID),
					'foc_iqref': read_signed_int(registers, MODBUS_FOC_IQREF),
					'foc_idref': read_signed_int(registers, MODBUS_FOC_IDREF),
					'foc_viq': read_signed_int(registers, MODBUS_FOC_VIQ),
					'foc_vid': read_signed_int(registers, MODBUS_FOC_VID),
					'foc_valpha': read_signed_int(registers, MODBUS_FOC_VALPHA),
					'foc_vbeta': read_signed_int(registers, MODBUS_FOC_VBETA),
					'foc_el_angle_dpp': read_signed_int(registers, MODBUS_FOC_EL_ANGLE_DPP),
					'foc_teref': read_signed_int(registers, MODBUS_FOC_TEREF),
					'voltage': read_signed_int(registers, MODBUS_VOLTAGE) / 1000 - 1,	 	# -1 is to recalibrate
					'collection_latency': time.time() - start,
				}
			except Exception as e:
				return {
					'id': name,
					'error': str(e)
				}

		with lock:
			if not instruments:
				event["error"] = "ERROR: modbus instruments not available. Plug the USB and hit Reset."

			else:
				start = time.time()
				event['devices'] = []
				event['devices'].append(read_all_registers(1, "motor1"))
				event['devices'].append(read_all_registers(2, "motor2"))
				event['collection_latency'] = time.time() - start
		return event

	def get_motion_stats(self):
		return self.motion_stats_schedule['last_event'] if 'last_event' in self.motion_stats_schedule else None


	def generate_voltage_stats_event(self):
		global instruments, lock

		# event basics
		event = {
			'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
			'type': "voltage_stats"
		}

		with lock:
			if not instruments:
				event["error"] = "ERROR: modbus instruments not available. Plug the USB and hit Reset."

			else:
				voltages = []
				error = ""
				try:
					event['motor1_voltage'] = instruments[1].read_register(MODBUS_VOLTAGE) / 1000 - 1	 	# -1 is to recalibrate
					voltages.append(event['motor1_voltage'])
				except Exception as e:
					error += "Motor1 Voltage Error: " + str(e) + "\n"

				try:
					event['motor2_voltage'] = instruments[1].read_register(MODBUS_VOLTAGE) / 1000 - 1 		# -1 is to recalibrate
					voltages.append(event['motor2_voltage'])
				except Exception as e:
					error += "Motor2 Voltage Error: " + str(e) + "\n"

				if len(voltages) > 0:
					event['voltage'] = sum(voltages) / len(voltages)
				else: 
					event['error'] = error

		return event

	def get_voltage_stats(self):
		return self.voltage_stats_schedule['last_event']

