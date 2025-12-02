from machine import Pin, PWM, SoftI2C
import ssd1306
import time

led = Pin("LED", Pin.OUT)
led.value(0)

def blink(times):
    led.value(0)
    for i in range(times*2):
        led.toggle()
        time.sleep(0.1)
    led.value(0)

def raise_my_exception(s):
    print(f"Exception {s} occured")
    blink(3)
    raise Exception(s)

# Motor Driver Class
class MotorDriver:
    BASE_VOLTAGE = 12
    SPEED_TO_ANGLE_SPEED = 8.3
    
    def __init__(self, in1_pin, in2_pin, en_pin, voltage=12):
        self.in1 = Pin(in1_pin, Pin.OUT)
        self.in2 = Pin(in2_pin, Pin.OUT)
        self.en = PWM(Pin(en_pin))
        self.en.freq(1000)
        self.current_speed = 0
        self.current_direction = 0
        self.last_direction = 0
        self.voltage = voltage
        
        # Inertia compensation parameters
        self.inertia_compensation = 0.9   # Start with 10% compensation
        self.compensation_duration = 0.025  # 50ms compensation pulse
        self.compensation_calibrated = False
        
        self.stop()
    
    def set_direction(self, direction):
        """Set motor direction: 1 = forward, -1 = reverse, 0 = stop"""
        self.current_direction = direction
        if direction == 1:  # Forward
            self.in1.value(1)
            self.in2.value(0)
        elif direction == -1:  # Reverse
            self.in1.value(0)
            self.in2.value(1)
        else:  # Stop
            self.in1.value(0)
            self.in2.value(0)
    
    def set_speed(self, speed, jerk=True):
        """Set motor speed (0-100)"""
        delta = speed - self.current_speed
        if jerk and abs(delta) > 40:
            if delta < 0:
                self.set_direction(-self.current_direction)
            self.set_speed(abs(delta) * (1 + self.inertia_compensation), False)
            time.sleep(self.compensation_duration)
            if delta < 0:
                self.set_direction(-self.current_direction)
        self.current_speed = max(0, min(100, speed))  # Clamp to 0-100
        pwm_value = int(self.current_speed * 655.35)  # Convert to 0-65535
        self.en.duty_u16(pwm_value)
        print(f"Set speed {self.current_speed}")
    
    def stop(self):
        # Complete stop
        self.set_speed(0)
        self.set_direction(0)
        
    def calibrate_inertia(self, test_speed=50, test_angle=180):
        """
        Calibrate inertia compensation for accurate angle movements
        """
        print("Calibrating inertia compensation...")
        
        # Test without compensation
        print("Testing without compensation...")
        
        self.move_angle(test_angle, test_speed, 1, use_compensation=False)
        
        # Test with different compensation values
        compensation_values = [0.05, 0.1, 0.15, 0.2, 0.25]
        
        for comp_val in compensation_values:
            self.inertia_compensation = comp_val
            
            self.move_angle(test_angle, test_speed, 1, use_compensation=True)
            time.sleep(1)
        

    
    def move_angle(self, angle_degrees, direction=1, use_compensation=True):
        """
        Move motor by approximate angle with inertia compensation
        angle_degrees: target angle in degrees
        rotation_time: time in seconds to complete the movement
        direction: 1 for forward, -1 for reverse
        """
    
        # Convert angle speed to motor speed (0-100)
        voltage_mul = self.BASE_VOLTAGE / self.voltage
        speed_to_set = 70 * voltage_mul
        
    
        # Cap speed to 100%
        if speed_to_set > 100:
            print(f"WARNING: required speed {speed_to_set:.1f}% exceeds maximum, capping to 100%")
            speed_to_set = 100
    
        rotation_time = angle_degrees / (speed_to_set * self.SPEED_TO_ANGLE_SPEED)
        print(f"Moving {angle_degrees}° in {rotation_time:.2f}s at {speed_to_set:.1f}% speed")
    
        # Start moving
        self.set_direction(direction)
        self.set_speed(speed_to_set)
    
        # Wait for calculated time
        time.sleep(rotation_time)
    
        # Stop with inertia compensation
        self.stop()
    
    def move_sine_wave(self, amplitude=180, frequency=1, duration=10):
        """Move motor in sine wave pattern using microseconds"""
        import math
    
        start_time = time.ticks_us()  # Returns microseconds as integer
        duration_us = duration * 1000000
        samples_per_second = 50
        sample_interval_us = 1000000 // samples_per_second  # 20000us per sample
    
        while time.ticks_diff(time.ticks_us(), start_time) < duration_us:
            elapsed_us = time.ticks_diff(time.ticks_us(), start_time)
            elapsed_seconds = elapsed_us / 1000000  # Convert to float seconds
        
            omega = 2 * math.pi * frequency
            phase = omega * elapsed_seconds
            sine_speed = amplitude * omega * math.cos(phase) / self.SPEED_TO_ANGLE_SPEED
            
            if sine_speed >= 0:
                self.set_direction(1)
                self.set_speed(sine_speed)
            else:
                self.set_direction(-1)
                self.set_speed(-sine_speed)
        
            # Sleep remaining time until next sample
            next_sample_us = start_time + ((elapsed_us // sample_interval_us) + 1) * sample_interval_us
            sleep_time_us = max(0, time.ticks_diff(next_sample_us, time.ticks_us()))
            print(sleep_time_us / 1000000)
            time.sleep_us(sleep_time_us)
    
        self.stop()
    
    def get_status(self):
        """Get motor status for display"""
        if self.current_direction == 1:
            return "FWD", self.current_speed
        elif self.current_direction == -1:
            return "REV", self.current_speed
        else:
            return "STOP", 0

# OLED Display Manager
class OLEDDisplay:
    def __init__(self, i2c):
        self.oled = ssd1306.SSD1306_I2C(128, 64, i2c)
        self.clear()
    
    def clear(self):
        self.oled.fill(0)
        self.oled.show()
    
    def update_display(self, motor1_status, motor2_status, mode="Manual", extra_info=""):
        """Update OLED with motor status"""
        m1_dir, m1_speed = motor1_status
        m2_dir, m2_speed = motor2_status
        
        self.oled.fill(0)
        
        # Header
        self.oled.text("MOTOR CONTROL", 15, 0)
        self.oled.hline(0, 10, 128, 1)
        
        # Motor 1 status
        self.oled.text(f"M1: {m1_speed:3d}% {m1_dir}", 0, 16)
        
        # Motor 2 status
        self.oled.text(f"M2: {m2_speed:3d}% {m2_dir}", 0, 28)
        
        # Mode and info
        self.oled.hline(0, 40, 128, 1)
        self.oled.text(f"Mode: {mode}", 0, 46)
        
        if extra_info:
            self.oled.text(extra_info, 0, 56)
        
        self.oled.show()
    
    def show_splash(self):
        """Show startup splash screen"""
        self.oled.fill(0)
        self.oled.text("MOTOR CONTROL", 15, 10)
        self.oled.text("SYSTEM READY", 20, 30)
        self.oled.text("Starting...", 35, 50)
        self.oled.show()
        time.sleep(2)

# Initialize hardware
print("Initializing system...")

# Demo sequences
def demo_sequence_1():
    """Both motors forward and reverse"""
    print("Demo 1: Forward/Reverse")
    display.update_display(motor1.get_status(), motor2.get_status(), "Demo 1", "Both FWD")
    
    # Both forward
    motor1.set_direction(1)
    motor2.set_direction(1)
    motor1.set_speed(60)
    motor2.set_speed(80)
    time.sleep(3)
    
    display.update_display(motor1.get_status(), motor2.get_status(), "Demo 1", "Both REV")
    
    # Both reverse
    motor1.set_direction(-1)
    motor2.set_direction(-1)
    motor1.set_speed(40)
    motor2.set_speed(70)
    time.sleep(3)

def demo_sequence_2():
    """Opposite directions"""
    print("Demo 2: Opposite directions")
    display.update_display(motor1.get_status(), motor2.get_status(), "Demo 2", "Opposite")
    
    # Opposite directions
    motor1.set_direction(1)
    motor2.set_direction(-1)
    motor1.set_speed(75)
    motor2.set_speed(75)
    time.sleep(3)

def demo_sequence_3():
    """Speed ramp test"""
    print("Demo 3: Speed ramp")
    
    # Ramp up speed
    for speed in range(0, 101, 10):
        motor1.set_direction(1)
        motor2.set_direction(1)
        motor1.set_speed(speed)
        motor2.set_speed(speed)
        display.update_display(motor1.get_status(), motor2.get_status(), "Demo 3", f"Ramp: {speed}%")
        time.sleep(0.5)
    
    time.sleep(1)
    
    # Ramp down speed
    for speed in range(100, -1, -10):
        motor1.set_direction(1)
        motor2.set_direction(1)
        motor1.set_speed(speed)
        motor2.set_speed(speed)
        display.update_display(motor1.get_status(), motor2.get_status(), "Demo 3", f"Ramp: {speed}%")
        time.sleep(0.5)

def stop_all():
    """Stop both motors"""
    motor1.stop()
    motor2.stop()
    display.update_display(motor1.get_status(), motor2.get_status(), "Stopped", "Ready")

# Add these demo functions after your existing demo sequences
def demo_angle_movement():
    """Demo precise angle movement"""
    print("Angle Movement Demo")
    display.update_display(motor1.get_status(), motor2.get_status(), "Angle Demo", "Calibrating...")
    time.sleep(1)
    
    # Move motor1 by specific angles
    angles = [90, 180, 270, 360, -90, -180]
    
    for angle in angles:
        direction = 1 if angle >= 0 else -1
        abs_angle = abs(angle)
        
        display.update_display(motor1.get_status(), motor2.get_status(), "Angle Demo", f"Moving: {angle}°")
        
        # Move motor1
        move_time = motor1.move_angle(abs_angle, 60, direction)
        
        display.update_display(motor1.get_status(), motor2.get_status(), "Angle Demo", f"Moved: {angle}°")
        time.sleep(1)

def demo_sine_wave():
    """Demo sine wave movement"""
    print("Sine Wave Demo")
    display.update_display(motor1.get_status(), motor2.get_status(), "Sine Demo", "Starting...")
    time.sleep(1)
    
    # Different sine wave patterns
    patterns = [
        {"amp": 30, "freq": 0.2, "dur": 10, "name": "Slow Sine"},
        {"amp": 70, "freq": 0.5, "dur": 8, "name": "Medium Sine"},
        {"amp": 40, "freq": 1.0, "dur": 6, "name": "Fast Sine"}
    ]
    
    for pattern in patterns:
        display.update_display(motor1.get_status(), motor2.get_status(), "Sine Demo", pattern["name"])
        time.sleep(1)
        
        start_time = time.time()
        motor1.move_sine_wave(pattern["amp"], pattern["freq"], pattern["dur"])
        
        display.update_display(motor1.get_status(), motor2.get_status(), "Sine Demo", f"Finished {pattern['name']}")
        time.sleep(1)

def demo_synchronized_sine():
    """Both motors moving in synchronized sine waves"""
    print("Synchronized Sine Demo")
    display.update_display(motor1.get_status(), motor2.get_status(), "Sync Sine", "Starting...")
    time.sleep(1)
    
    import math
    import _thread
    
    duration = 10
    start_time = time.time()
    samples_per_second = 50
    
    def motor1_sine():
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            phase = 2 * math.pi * 0.3 * elapsed
            sine_speed = 40 * math.sin(phase)
            
            if sine_speed >= 0:
                motor1.set_direction(1)
                motor1.set_speed(abs(sine_speed))
            else:
                motor1.set_direction(-1)
                motor1.set_speed(abs(sine_speed))
            
            time.sleep(1.0 / samples_per_second)
        motor1.stop()
    
    def motor2_sine():
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            phase = 2 * math.pi * 0.3 * elapsed + math.pi/2  # 90° phase shift
            sine_speed = 40 * math.sin(phase)
            
            if sine_speed >= 0:
                motor2.set_direction(1)
                motor2.set_speed(abs(sine_speed))
            else:
                motor2.set_direction(-1)
                motor2.set_speed(abs(sine_speed))
            
            time.sleep(1.0 / samples_per_second)
        motor2.stop()
    
    # Run both motors (this is simplified - for true parallel need _thread)
    # For now, run them sequentially
    motor1_sine()
    motor2_sine()
    
    display.update_display(motor1.get_status(), motor2.get_status(), "Sync Sine", "Finished")

try:
    # Motors
    motor1 = MotorDriver(in1_pin=21, in2_pin=20, en_pin=22, voltage=12)
    motor2 = MotorDriver(in1_pin=19, in2_pin=18, en_pin=17, voltage=12)

    # OLED Display
    i2c = SoftI2C(scl=Pin(14), sda=Pin(15))
    display = OLEDDisplay(i2c)

    # Show startup screen
    display.show_splash()
    
    motor1.move_sine_wave(amplitude=300, frequency=0.4, duration=10)
except:
    # Clean shutdown
    print("Stopping motors...")
    try:
        motor1.stop()
        motor2.stop()
        display.clear()
        display.oled.text("SYSTEM", 40, 20)
        display.oled.text("STOPPED", 35, 40)
        display.oled.show()
    except:
        pass
    blink(2)


#motor1.move_sine_wave(180, 0.5, 10)
#motor1.move_angle(360, 5, 1, False)