import board
from adafruit_led_animation import color
import math
import neopixel_spi as neopixel
import time

'''
gamma = [
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,
    1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  2,  2,  2,  2,  2,  2,
    2,  3,  3,  3,  3,  3,  3,  3,  4,  4,  4,  4,  4,  5,  5,  5,
    5,  6,  6,  6,  6,  7,  7,  7,  7,  8,  8,  8,  9,  9,  9, 10,
   10, 10, 11, 11, 11, 12, 12, 13, 13, 13, 14, 14, 15, 15, 16, 16,
   17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25,
   25, 26, 27, 27, 28, 29, 29, 30, 31, 32, 32, 33, 34, 35, 35, 36,
   37, 38, 39, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 50,
   51, 52, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68,
   69, 70, 72, 73, 74, 75, 77, 78, 79, 81, 82, 83, 85, 86, 87, 89,
   90, 92, 93, 95, 96, 98, 99,101,102,104,105,107,109,110,112,114,
  115,117,119,120,122,124,126,127,129,131,133,135,137,138,140,142,
  144,146,148,150,152,154,156,158,160,162,164,167,169,171,173,175,
  177,180,182,184,186,189,191,193,196,198,200,203,205,208,210,213,
  215,218,220,223,225,228,231,233,236,239,241,244,247,249,252,255 ]
'''

gamma = 2.8

def coloradj(col, intensity):
    if intensity > 1.0:
        intensity = intensity % 1
    return color.calculate_intensity(col, pow(intensity, gamma))

headwidth = 1.6
endwidth = 6

"""
speed in revolutions per second
fps is animation frames per second
"""
class NeoVolume:
    def __init__(self, num_pixels=12, \
            vol_min=-100, vol_max=900, curr_vol=400, muted=False, \
            color=color.JADE, mute_color=color.RED, \
            intensity=0.7, min_intensity = 0.4, mute_intensity=0.3, \
            speed=10, fps=60):

        self.min = vol_min
        self.max = vol_max
        self.vol = curr_vol
        self.muted = muted
        self.color = color
        self.mute_color = mute_color
        self.intensity = intensity
        self.min_intensity = min_intensity
        self.mute_intensity = mute_intensity
        self.speed = speed
        self.fps = fps

        # Using hardware SPI
        self.dots = neopixel.NeoPixel_SPI(board.SPI(),
                                          num_pixels,
                                          pixel_order=neopixel.GRB,
                                          auto_write=False)

        self._output()

        # Create internal thread
        # Create runloop on thread
        # Block waiting for new data in queue
        # When new data, run animation in fps until finished
        # Signal animation in progress using async lock
        #   without blocking thread

    def set_volume(self, volume):
        if volume < self.min or volume > self.max:
            return
        self.vol = volume
        self._output()

    def set_mute(self, mute):
        mute = not not mute
        if mute == self.muted:
            return
        self.muted = mute
        self._output()

    def _output(self):
        if self.muted:
            self.dots.fill(coloradj(self.mute_color, self.mute_intensity))
            self.dots.show()
            return
        self._clear()
        self._output_volume(self.vol)
        self.dots.show()

    def _clear(self):
        for dot in range(len(self.dots)):
            self.dots[dot] = color.BLACK

    def _output_volume(self, volume):
        avol = volume - self.min
        rang = self.max - self.min
        head = avol*1.0/rang * len(self.dots)
        tail = head - headwidth
        end = head - endwidth

        if head >= len(self.dots):
            headi = 1.0
            headidx = len(self.dots)-1
        else:
            headi = head
            if headi > 1.0:
                headi = headi % 1
            headidx = int(math.floor(head))
        tailidx = int(math.floor(tail))

        if tail >= 0:
            for trail in range(0, int(math.floor(tail))):
                if trail >= end:
                    traili = ((trail+1-end)**2 - (trail-end)**2)/2/(tail-end)
                    traili = traili*self.intensity
                    if traili < self.min_intensity:
                        traili = self.min_intensity
                else:
                    traili = self.min_intensity
                self.dots[trail] = coloradj(self.color, traili*self.intensity)
            headpart = math.floor(tail) + 1 - tail
            traili = ((tail-end)**2 - (tailidx-end)**2)/2/(tail-end)
            intensity = (headpart+traili)*self.intensity
            self.dots[tailidx] = coloradj(self.color, intensity)
        for dot in range(max(tailidx+1, 0), headidx):
            self.dots[dot] = coloradj(self.color, self.intensity)
        headi = self.intensity*headi
        self.dots[headidx] = coloradj(self.color, headi)

