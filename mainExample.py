#Import libraries
import time 
import machine
import micropython
from machine import ADC
from machine import Pin
from lib.onewire import OneWire
from lib.onewire import DS18X20
from lib.mqtt import MQTTClient

#initiate mqtt
mqtt_client = MQTTClient(
    "pico-client",
    "HOST IP ADDRESS"  # Change this to your actual IP address
)
mqtt_client.connect()

#initiate DS18B20 (temperature sensor)
dat = Pin(26)
ow = OneWire(dat)
roms = ow.scan()
temp_sensor = DS18X20(ow)

#initate knock sensor
knock_sensor = Pin(27, Pin.IN, Pin.PULL_UP)
knock_triggered = False

def knock_handler(pin):
    global knock_triggered
    knock_triggered = True

knock_sensor.irq(trigger = Pin.IRQ_FALLING, handler = knock_handler)

#initiate buzzer
buzzer = Pin(2, Pin.OUT)

#initiate LED
led_r = Pin(18, Pin.OUT)
led_g = Pin(19, Pin.OUT)
led_b = Pin(20, Pin.OUT)

# Thresholds
TEMP_THRESHOLD = 31  # degrees celsius
INACTIVITY_TIMEOUT = 10 # after 10 seconds, the exercise will be aborted
TEMP_READ_INTERVAL = 2.0 # the interval of which the temperature will be properly read from the sensor

def leds_off():
    led_r.on()
    led_g.on()
    led_b.on()

def white_led():
    led_r.off()
    led_g.off()
    led_b.off()

def green_led():
    led_r.on()
    led_g.off()
    led_b.on()

def red_led():
    led_r.off()
    led_g.on()
    led_b.on()

# breathing exercise according to the 4-7-8 method, x3 to ensure it is around a minute to get proper time 
# for destress
def breathing_guide(times=3):
    for _ in range(times):
        print("Inhale")
        led_r.on()
        led_g.on()
        led_b.off()
        time.sleep(4)

        print("Hold breath")
        led_r.off()
        time.sleep(7)

        print("Exhale")
        leds_off()
        time.sleep(8)

def read_temp():
    global last_temp, last_temp_time

    now = time.time()
    #  only new read from sensor every 2 seconds, otherwise use the last measured temp
    # this is to decrease the delay that inevitably will come from getting a proper reading
    if now - last_temp_time >= TEMP_READ_INTERVAL:
        temp_sensor.start_conversion()
        time.sleep_ms(750)
        for rom in roms:
            temp_c = temp_sensor.read_temp_async(rom)
            if temp_c is not None:
                last_temp = temp_c
        last_temp_time = now
    return last_temp

def pause_beep():
    for _ in range(3):
        buzzer.on()
        time.sleep(0.2)
        buzzer.off()

def abort_beep():
    buzzer.on()
    time.sleep(1.5)
    buzzer.off()

def publish_status(status):
    mqtt_client.publish("breathing/status", status)

def publish_temp(temp):
    mqtt_client.publish("breathing/temperature", str(temp))

last_temp = None
last_temp_time = 0
while True:
    while True:
        current_temp = read_temp()
        if current_temp >= TEMP_THRESHOLD:
            break
        leds_off()
        time.sleep(0.5)
        publish_temp(current_temp)
    
    print("Hand detected. Waiting for knock...")
    white_led()
    inactivity_start = None

    while True:
        current_temp = read_temp()

        if current_temp < TEMP_THRESHOLD:
            if inactivity_start is None:
                inactivity_start = time.time()
                print("Hand removed. Put your finger back on the sensor to continue.")
                pause_beep()
                red_led()
                publish_status("paused")
            elif time.time() - inactivity_start > INACTIVITY_TIMEOUT:
                print("Inactive for 10 seconds. Exercise interrupted.")
                abort_beep()
                red_led()
                publish_status("aborted")
                break
            else:
                time.sleep(0.1)
                continue
        else:
            if inactivity_start:
                print("Hand returned. Exercise will continue.")
                publish_status("resumed")
            inactivity_start = None

        publish_temp(current_temp)
        
        if knock_triggered:
            knock_triggered = False
            publish_status("started")
            buzzer.on()
            time.sleep(0.5)
            buzzer.off()
            breathing_guide()
            buzzer.on()
            time.sleep(0.5)
            buzzer.off()
            green_led()
            time.sleep(1.5)
            print("Breathing exercise finished")
            publish_status("completed")
            break
   
        time.sleep(0.1)




    

    
