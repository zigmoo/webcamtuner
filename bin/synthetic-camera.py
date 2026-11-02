#!/usr/bin/env python3
"""Bounded, clock-paced diagnostic source. No capture devices are opened."""
import signal
import sys
import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

Gst.init(None)
pipeline = Gst.parse_launch(
    'videotestsrc is-live=true pattern=ball ! '
    'video/x-raw,width=1280,height=720,framerate=30/1,format=YUY2 ! '
    'timeoverlay ! queue max-size-buffers=1 max-size-bytes=0 max-size-time=0 leaky=downstream ! '
    'pipewiresink mode=provide sync=false client-name=WebcamTuner '
    'stream-properties="props,node.name=webcamtuner.test,node.description=WebcamTuner,media.class=Video/Source,media.role=Camera"')
# A sink-provided clock may pause without readers; use the monotonic system clock
# and a latest-frame queue so reconnecting never replays an accumulated timeline.
pipeline.use_clock(Gst.SystemClock.obtain())
loop = GLib.MainLoop()
failed = False


def message(_bus, msg):
    global failed
    if msg.type == Gst.MessageType.ERROR:
        error, debug = msg.parse_error()
        print(str(error), file=sys.stderr, flush=True)
        failed = True
        loop.quit()
    elif msg.type == Gst.MessageType.EOS:
        loop.quit()


bus = pipeline.get_bus()
bus.add_signal_watch()
bus.connect('message', message)
for sig in (signal.SIGINT, signal.SIGTERM):
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
try:
    if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
        raise RuntimeError('Could not start the test source')
    loop.run()
finally:
    pipeline.set_state(Gst.State.NULL)
sys.exit(1 if failed else 0)
