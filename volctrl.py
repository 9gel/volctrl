#!/usr/bin/env python

from __future__ import print_function

# Force pynput to use uinput for keyboard
import os
os.environ["PYNPUT_BACKEND"] = "dummy"
os.environ["PYNPUT_BACKEND_KEYBOARD"] = "uinput"

import alsaaudio
import asyncio
import concurrent
import contextvars
import evdev
import functools
import getopt
import logging
import pprint
import select
import signal
import neovolume
from gpiozero import RotaryEncoder
import sys
import threading
import traceback

#KEY_MTE = evdev.ecodes.KEY_M           # 50   # KEY_M
#KEY_VUP = evdev.ecodes.KEY_RIGHT       # 106  # KEY_RIGHT
#KEY_VDN = evdev.ecodes.KEY_LEFT        # 105  # KEY_LEFT
KEY_QUIT = evdev.ecodes.KEY_KP1         # 79

KEY_MTE = evdev.ecodes.KEY_MUTE        # 113   # KEY_MUTE
KEY_VUP = evdev.ecodes.KEY_VOLUMEUP    # 114  # KEY_VOLUMEUP
KEY_VDN = evdev.ecodes.KEY_VOLUMEDOWN  # 115  # KEY_VOLUMEDOWN
#KEY_QUIT = evdev.ecodes.KEY_ESC

VOL_STEP = 0.03

ROTARY_PIN_A = 22
ROTARY_PIN_B = 27
ROTATY_PIN_M = 17

def list_cards():
    print("Available sound cards:")
    for i in alsaaudio.card_indexes():
        (name, longname) = alsaaudio.card_name(i)
        print("  %d: %s (%s)" % (i, name, longname))

def list_mixers(kwargs):
    print("Available mixer controls:")
    for m in alsaaudio.mixers(**kwargs):
        print("  '%s'" % m)

def get_mixer(name, kwargs):
    try:
        return alsaaudio.Mixer(name, **kwargs)
    except alsaaudio.ALSAAudioError:
        print("No such mixer: '%s'" % name, file=sys.stderr)
        sys.exit(1)

def show_mixer(mixer):
    print("Mixer name: '%s'" % mixer.mixer())
    volcap = mixer.volumecap()
    print("Capabilities: %s %s" % (' '.join(volcap),
                                   ' '.join(mixer.switchcap())))

    if "Volume" in volcap or "Joined Volume" in volcap or "Playback Volume" in volcap:
        pmin, pmax = mixer.getrange(alsaaudio.PCM_PLAYBACK)
        pmin_keyword, pmax_keyword = mixer.getrange(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
        pmin_default, pmax_default = mixer.getrange()
        assert pmin == pmin_keyword
        assert pmax == pmax_keyword
        assert pmin == pmin_default
        assert pmax == pmax_default
        print("Raw playback volume range {}-{}".format(pmin, pmax))
        pmin_dB, pmax_dB = mixer.getrange(units=alsaaudio.VOLUME_UNITS_DB)
        print("dB playback volume range {}-{}".format(pmin_dB / 100.0, pmax_dB / 100.0))

    if "Capture Volume" in volcap or "Joined Capture Volume" in volcap:
        # Check that `getrange` works with keyword and positional arguments
        cmin, cmax = mixer.getrange(alsaaudio.PCM_CAPTURE)
        cmin_keyword, cmax_keyword = mixer.getrange(pcmtype=alsaaudio.PCM_CAPTURE, units=alsaaudio.VOLUME_UNITS_RAW)
        assert cmin == cmin_keyword
        assert cmax == cmax_keyword
        print("Raw capture volume range {}-{}".format(cmin, cmax))
        cmin_dB, cmax_dB = mixer.getrange(pcmtype=alsaaudio.PCM_CAPTURE, units=alsaaudio.VOLUME_UNITS_DB)
        print("dB capture volume range {}-{}".format(cmin_dB / 100.0, cmax_dB / 100.0))

    volumes = mixer.getvolume()
    volumes_raw = mixer.getvolume(units=alsaaudio.VOLUME_UNITS_RAW)
    volumes_dB = mixer.getvolume(units=alsaaudio.VOLUME_UNITS_DB)
    for i in range(len(volumes)):
        print("Channel %i playback volume: %i (%i%%, %.1f dB)" % (i, volumes_raw[i], volumes[i], volumes_dB[i] / 100.0))

    volumes = mixer.getvolume(pcmtype=alsaaudio.PCM_CAPTURE)
    volumes_raw = mixer.getvolume(pcmtype=alsaaudio.PCM_CAPTURE, units=alsaaudio.VOLUME_UNITS_RAW)
    volumes_dB = mixer.getvolume(pcmtype=alsaaudio.PCM_CAPTURE, units=alsaaudio.VOLUME_UNITS_DB)
    for i in range(len(volumes)):
        print("Channel %i capture volume: %i (%i%%, %.1f dB)" % (i, volumes_raw[i], volumes[i], volumes_dB[i] / 100.0))

    try:
        mutes = mixer.getmute()
        for i in range(len(mutes)):
            if mutes[i]:
                print("Channel %i is muted" % i)
    except alsaaudio.ALSAAudioError:
        # May not support muting
        pass

    try:
        recs = mixer.getrec()
        for i in range(len(recs)):
            if recs[i]:
                print("Channel %i is recording" % i)
    except alsaaudio.ALSAAudioError:
        # May not support recording
        pass

def find_inputs():
    devs = [evdev.InputDevice(path) for path in evdev.list_devices()]
    return list(map(lambda dc: dc[0], 
                    filter(lambda dc: \
                            evdev.ecodes.EV_KEY in dc[1] \
                            and KEY_VUP in dc[1][evdev.ecodes.EV_KEY] \
                            and KEY_VDN in dc[1][evdev.ecodes.EV_KEY] \
                            and KEY_MTE in dc[1][evdev.ecodes.EV_KEY], \
                            map(lambda d: (d, d.capabilities()), devs))))

def get_volume(mixer):
    vmin, vmax = mixer.getrange(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
    volumes = mixer.getvolume(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
    volume = volumes[0]
    muted = False
    try:  # control might not support mute
        mutes = mixer.getmute()
        muted = mutes[0]
    except:
        pass
    return (muted, volume, vmin, vmax)

neo = None

def output_volume(mixer):
    global neo
    muted, volume, vmin, vmax = get_volume(mixer)
    m = 'muted'
    if not muted:
        m = 'unmuted'
    sys.stdout.write("\r%-7s | %7d:%7d:%7d" % (m, vmin, volume, vmax))
    sys.stdout.flush()

    if not neo:
        neo = neovolume.NeoVolume(vol_min=vmin, vol_max=vmax, curr_vol=volume, muted=muted)
    neo.set_mute(muted)
    neo.set_volume(volume)

def show_volume(mixername, kwargs, quitter):
    loop = asyncio.events.get_running_loop()

    def _listen_mixer(mixername, kwargs):
        mixer = get_mixer(mixername, kwargs)
        pd = mixer.polldescriptors()
        fd, emask = pd[0]
        p = select.poll()
        p.register(fd, emask)
        first = False
        while True:
            out = p.poll(500)
            if not out:
                if not first:
                    output_volume(mixer)
                    first = True
                continue
            pfd, pevt = out[0]
            if pfd != fd or pevt&select.POLLHUP or pevt&select.POLLRDHUP:
                sys.stderr.write("Mixer listener got a HUP\n")
                sys.stderr.flush()
                loop.call_soon_threadsafe(quitter)
                return
            output_volume(mixer)
            mixer.handleevents()
    
    listener = threading.Thread(target=_listen_mixer, \
            args=(mixername, kwargs), daemon=True)
    listener.start()

def change(ecode, mixer):
    muted, volume, vmin, vmax = get_volume(mixer)
    if ecode == KEY_MTE:
        try:  # control might not support mute
            mixer.setmute(not muted)
            muted = not muted
        except:
            pass
        return

    if ecode == KEY_VUP:
        volume = min(int(volume + VOL_STEP*(vmax-vmin))+vmin, vmax)
    elif ecode == KEY_VDN:
        volume = max(int(volume - VOL_STEP*(vmax-vmin))+vmin, 0)
    else:
        return
    mixer.setvolume(volume, pcmtype=alsaaudio.PCM_PLAYBACK, \
            units=alsaaudio.VOLUME_UNITS_RAW)

async def input_control(device, mixer, quitter):
    #print("Device: {} {} {}".format(device.name, device.path, device.phys))
    try:
        async for event in device.async_read_loop():
            if event.type != evdev.ecodes.EV_KEY \
                    or event.value != evdev.events.KeyEvent.key_up:
                continue
            if event.code == KEY_QUIT:
                quitter()
            elif event.code == KEY_MTE or event.code == KEY_VUP or event.code == KEY_VDN:
                await change(event.code, mixer)
    except Exception as e:
        sys.stderr.write("Error reading from device {} ({}, {}):\n{}\n".format(\
                device.name, device.path, device.phys, e))
        sys.stderr.flush()

async def rotary_input(mixer, quitter):
    loop = asyncio.events.get_running_loop()

    rotor = RotaryEncoder(ROTARY_PIN_A, ROTARY_PIN_B)
    rotor.when_rotated_clockwise = functools.partial(\
            loop.call_soon_threadsafe, change, KEY_VUP, mixer)
    rotor.when_rotated_counter_clockwise = functools.partial(\
            loop.call_soon_threadsafe, change, KEY_VDN, mixer)

    await asyncio.Event().wait()

async def ctrl_show(mixername, kwargs):
    mixer = get_mixer(mixername, kwargs)

    inputs = find_inputs()
    if not inputs:
        sys.stderr.write("Cannot find any viable volume inputs\n")
        return
    quitq = asyncio.Queue()
    def quitter():
        quitq.put_nowait(True)

    os.system("stty -echo")
    print("Press {} to quit".format(evdev.ecodes.KEY[KEY_QUIT]))
    async def all_tasks():
        async with asyncio.TaskGroup() as cmtg:
            for dev in inputs:
                cmtg.create_task(input_control(dev, mixer, quitter))
            cmtg.create_task(rotary_input(mixer, quitter))

    async def wait_quit(cmtg_task):
        await quitq.get()
        cmtg_task.cancel()

    show_volume(mixername, kwargs, quitter)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(wait_quit(tg.create_task(all_tasks())))
    print()
    os.system("stty echo")

    mixer.close()

def run():
    # Debug logging
    #logging.basicConfig(level=logging.DEBUG)

    kwargs = {}
    opts, args = getopt.getopt(sys.argv[1:], 'c:d:?h')
    for o, a in opts:
        if o == '-c':
            kwargs = { 'cardindex': int(a) }
        elif o == '-d':
            kwargs = { 'device': a }
        else:
            usage()

    list_cards()
    list_mixers(kwargs)

    if len(args) < 1:
        return

    show_mixer(get_mixer(args[0], kwargs))
    asyncio.run(ctrl_show(args[0], kwargs))

def usage():
    print('usage: mixertest.py [-c <card>] [control]',
          file=sys.stderr)
    sys.exit(2)

if __name__ == '__main__':
    run()

