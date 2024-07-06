#!/usr/bin/python3
import Adafruit_PCA9685

class Move:
	def __init__(self):
		self.look_right_max=120
		self.look_left_max=576
		self.span_of_vision=180
		self.degrees_per_degree=(self.look_left_max - self.look_right_max)/self.span_of_vision
		self.degrees_per_meter=0
		self.current=300

		self.pwm = Adafruit_PCA9685.PCA9685()
		self.pwm.set_pwm_freq(60)

	def left(self, pixels, radius):
		self.turn(-pixels*radius/500)

	def right(self, pixels, radius):
		self.turn(pixels*radius/500)

	def turn(self, degrees):
		self.current -= degrees * self.degrees_per_degree
		self.current = int(min(max(self.current, self.look_right_max), self.look_left_max))
		self.pwm.set_pwm(1, 0, self.current)

	def move(self, meters):
		pass
