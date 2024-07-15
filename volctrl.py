#!/usr/bin/env python

from __future__ import print_function

import alsaaudio
import asyncio
import getopt
import keyboard
import os
import select
import signal
import sys

def list_cards():
    print("Available sound cards:")
    for i in alsaaudio.card_indexes():
        (name, longname) = alsaaudio.card_name(i)
        print("  %d: %s (%s)" % (i, name, longname))

def list_mixers(kwargs):
    print("Available mixer controls:")
    for m in alsaaudio.mixers(**kwargs):
        print("  '%s'" % m)

def show_mixer(name, kwargs):
    # Demonstrates how mixer settings are queried.
    try:
        mixer = alsaaudio.Mixer(name, **kwargs)
    except alsaaudio.ALSAAudioError:
        print("No such mixer", file=sys.stderr)
        sys.exit(1)

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

def control_mixer(mixer):
    print("Press esc key to quit")

    channel = alsaaudio.MIXER_CHANNEL_ALL
    pmin, pmax = mixer.getrange(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
    volumes = mixer.getvolume(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
    volume = volumes[0]
    muted = False
    try:  # control might not support mute
        mutes = mixer.getmute()
        muted = mutes[0]
    except:
        pass

    os.system("stty -echo")
    while True:
        try:
            e = keyboard.read_event()
        except Exception as exp:
            print("Error reading keyboard: %s" % exp)
            sys.stdout.flush()
            os.system("stty echo")
            return
        if e.event_type == keyboard.KEY_UP:
            if e.name == 'left':
                volume = max(int(volume - 0.05*pmax), 0)
            elif e.name == 'right':
                volume = min(int(volume + 0.05*pmax), pmax)
            elif e.name == 'm':
                try:  # control might not support mute
                    mixer.setmute(not muted)
                    muted = not muted
                except:
                    pass
                continue
            elif e.name == 'esc':
                return
            else:
                continue
            mixer.setvolume(volume, pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)

def output_volume(mixer):
    vmin, vmax = mixer.getrange(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
    volumes = mixer.getvolume(pcmtype=alsaaudio.PCM_PLAYBACK, units=alsaaudio.VOLUME_UNITS_RAW)
    volume = volumes[0]
    muted = False
    try:  # control might not support mute
        mutes = mixer.getmute()
        muted = mutes[0]
    except:
        pass
    m = 'muted'
    if not muted:
        m = 'unmuted'
    sys.stdout.write("\r%-7s | %3d:%3d:%3d" % (m, vmin, volume, vmax))
    sys.stdout.flush()

def listen_mixer(mixer):
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
            return
        output_volume(mixer)
        mixer.handleevents()
        
def usage():
    print('usage: mixertest.py [-c <card>] [control]',
          file=sys.stderr)
    sys.exit(2)

async def mixer(name, kwargs):
    try:
        mixer = alsaaudio.Mixer(name, **kwargs)
    except alsaaudio.ALSAAudioError:
        print("No such mixer", file=sys.stderr)
        sys.exit(1)

    async with asyncio.TaskGroup() as tg:
        lisn = tg.create_task(asyncio.to_thread(listen_mixer, mixer))
        ctrl = tg.create_task(asyncio.to_thread(control_mixer, mixer))
        await ctrl  # when control exists, cancel the listener
        lisn.cancel()

    mixer.close()

def run():
    signal.signal(signal.SIGINT, lambda *args: None)
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

    if len(args) == 1:
        show_mixer(args[0], kwargs)
        asyncio.run(mixer(args[0], kwargs))

if __name__ == '__main__':
    run()

