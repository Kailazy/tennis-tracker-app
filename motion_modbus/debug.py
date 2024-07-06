import getkey
import os
import minimalmodbus
command = os.popen('ls /dev/tty* | grep -i usb')
usbport = command.read().split("\n")[0]
instruments = [minimalmodbus.Instrument(usbport, 0), #, close_port_after_each_call=True), 
		minimalmodbus.Instrument(usbport, 1), #, close_port_after_each_call=True), 
		minimalmodbus.Instrument(usbport, 2)] #, close_port_after_each_call=True)]
def regs(id):
	columns = "MODBUS_REQUESTED_POSITION,MODBUS_REQUESTED_DURATION,MODBUS_VOLTAGE,MODBUS_POSITION,MODBUS_AVG_SPEED,MODBUS_REQUESTED_SPEED,MODBUS_DEFAULT_CONTROL_MODE,MODBUS_SPEED,MODBUS_TORQUE_REF,MODBUS_DEFAULT_TORQUE_REF,MODBUS_DEFAULT_ID_REF,MODBUS_CURRENT_AMPLITUDE,MODBUS_VOLTAGE_AMPLITUDE,MODBUS_FOC_IA,MODBUS_FOC_IB,MODBUS_FOC_ALPHA,MODBUS_FOC_BETA,MODBUS_FOC_IQ,MODBUS_FOC_ID,MODBUS_FOC_IQREF,MODBUS_FOC_IDREF,MODBUS_FOC_VIQ,MODBUS_FOC_VID,MODBUS_FOC_VALPHA,MODBUS_FOC_VBETA,MODBUS_FOC_EL_ANGLE_DPP,MODBUS_FOC_TEREF,MODBUS_EMPTY,MODBUS_POSITION_REF"
	print(columns)
	while 42:
		try:
			regs = list(map(lambda x: x if x < 32768 else +x-65536, instruments[id].read_registers(0,32)))
			regs[30] = regs[31] + (regs.pop(30) + (1 if regs[30] < 0 else 0) ) * 65536
			regs[4] = regs[5] + (regs.pop(4) + (1 if regs[4] < 0 else 0) ) * 65536
			regs[0] = regs[1] + (regs.pop(0) + (1 if regs[0] < 0 else 0) ) * 65536
			regs = ', '.join(map(lambda x: str(x).rjust(6), regs))
			print('%s        \r'%regs, end='')
		except:
			continue
		if getkey.getkey(blocking=False) != '':
			print('You Pressed A Key!')
			break  # finishing the loop
