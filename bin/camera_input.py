"""Capture a physical camera through PipeWire so other consumers can share it."""
import json
from pathlib import Path
import subprocess


def camera_serial(camera, nodes=None):
    path = Path(camera).resolve()
    if nodes is None:
        nodes = json.loads(subprocess.check_output(['pw-dump'], timeout=5))
    for node in nodes:
        props = node.get('info', {}).get('props', {})
        device = props.get('api.v4l2.path')
        if props.get('media.class') == 'Video/Source' and device and Path(device).resolve() == path:
            serial = str(props.get('object.serial', ''))
            if serial.isdecimal():
                return serial
    raise RuntimeError('This camera is not available through PipeWire. Check its connection and camera permissions.')


class SharedCameraInput:
    """A bounded reader of the brokered camera; never opens /dev/video directly."""
    def __init__(self, camera, mode):
        import gi
        gi.require_version('Gst', '1.0')
        gi.require_version('GstVideo', '1.0')
        from gi.repository import Gst, GstVideo
        self.Gst, self.GstVideo = Gst, GstVideo
        self.pipeline = None
        self.width, self.height = int(mode['width']), int(mode['height'])
        self.fps = min(float(mode['fps']), 30)
        if not (0 < self.width <= 8192 and 0 < self.height <= 8192 and 0 < self.fps <= 30):
            raise ValueError('Invalid camera capture mode.')
        serial = camera_serial(camera)
        Gst.init(None)
        jpeg = mode.get('fourcc') == 'MJPG'
        self.pipeline = Gst.parse_launch(
            f'pipewiresrc always-copy=true min-buffers=4 max-buffers=8 target-object={serial} ! '
            'capsfilter name=source_mode ! ' + ('jpegdec ! ' if jpeg else '') + 'videoconvert ! '
            'video/x-raw,format=BGR ! appsink name=frames sync=false max-buffers=1 drop=true')
        from fractions import Fraction
        rate = Fraction(self.fps).limit_denominator(1001)
        dimensions = f'width={self.width},height={self.height},framerate={rate.numerator}/{rate.denominator}'
        media = 'image/jpeg' if jpeg else 'video/x-raw'
        raw_format = {'YUYV': 'YUY2', 'NV12': 'NV12'}.get(mode.get('fourcc'))
        if not jpeg and raw_format:
            media += ',format=' + raw_format
        self.pipeline.get_by_name('source_mode').set_property('caps', Gst.Caps.from_string(f'{media},{dimensions}'))
        self.sink = self.pipeline.get_by_name('frames')
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            message = self.pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
            detail = str(message.parse_error()[0]) if message else 'No camera format could be negotiated.'
            self.release()
            raise RuntimeError('Could not start shared camera capture: ' + detail)

    def read(self):
        Gst = self.Gst
        message = self.pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if message:
            detail = str(message.parse_error()[0]) if message.type == Gst.MessageType.ERROR else 'Camera stream ended.'
            raise RuntimeError('Shared camera capture failed: ' + detail)
        sample = self.sink.emit('try-pull-sample', 500 * Gst.MSECOND)
        if sample is None:
            return None
        info = self.GstVideo.VideoInfo.new_from_caps(sample.get_caps())
        if info.width != self.width or info.height != self.height:
            raise RuntimeError('Camera did not accept its selected full-resolution mode.')
        buffer = sample.get_buffer()
        data = buffer.extract_dup(0, buffer.get_size())
        stride = info.stride[0]
        if stride < self.width * 3 or len(data) < stride * self.height:
            raise RuntimeError('Camera returned an incomplete frame.')
        return {'data': data, 'width': info.width, 'height': info.height, 'stride': stride}

    def release(self):
        if self.pipeline is not None:
            self.pipeline.set_state(self.Gst.State.NULL)
            self.pipeline = None
