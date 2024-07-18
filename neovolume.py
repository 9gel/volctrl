import board
from adafruit_led_animation import color
import math
import neopixel_spi as neopixel
import time

"""
headwith in pixels
speed in revolutions per second
fps is animation frames per second
"""
class NeoVolume:
    def __init__(self, num_pixels=12, \
            vol_min=-100, vol_max=900, curr_vol=400, muted=False, \
            color=color.JADE, mute_color=color.RED, \
            head_intensity=0.3, tail_intensity=0.02, mute_intensity=0.3, \
            headwidth=1.3, speed=10, fps=200):

        self.min = vol_min
        self.max = vol_max
        self.vol = curr_vol
        self.muted = muted
        self.color = color
        self.mute_color = mute_color
        self.head_intensity = head_intensity
        self.tail_intensity = tail_intensity
        self.mute_intensity = mute_intensity
        self.headwidth = headwidth
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
        # When new data, run animation in fps until finished using async lock
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
            self.dots.fill(color.calculate_intensity(self.mute_color, self.mute_intensity))
            self.dots.show()
            return
        avol = self.vol - self.min
        rang = self.max - self.min
        head = int(math.floor(avol * len(self.dots) / rang)) - 1
        headi = 1.0
        if (avol * len(self.dots)) % rang != 0:
            head = head + 1
            headi = (avol*1.0/rang * len(self.dots)) % 1
        if head < 0:
            head = 0
            headi = 0.0
        tail = avol*1.0/rang * len(self.dots) - self.headwidth
        taili = 1.0
        if tail > 0:
            taili = tail % 1
        tail = int(math.floor(tail))
        if tail >= 0:
            for dot in range(tail):
                self.dots[dot] = color.calculate_intensity(self.color, self.tail_intensity)
            self.dots[tail] = color.calculate_intensity(self.color,
                                                        self.head_intensity \
                                                                * (1-taili+self.tail_intensity))
        for dot in range(max(tail+1, 0), head):
            self.dots[dot] = color.calculate_intensity(self.color, self.head_intensity)
        self.dots[head] = color.calculate_intensity(self.color, self.head_intensity*headi)
        for dot in range(head+1, len(self.dots)):
            self.dots[dot] = color.BLACK
        self.dots.show()

