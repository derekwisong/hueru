import gi
import threading
import numpy as np

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GstApp, GLib

class ScreenScanner:
    def __init__(self, width=160, height=90):
        Gst.init(None)
        self.width = width
        self.height = height
        self.latest_frame = None
        
        # Optimized pipeline.
        # We set media.role=Screen to hint to PipeWire that we want to capture a
        # screen. This should trigger the desktop portal to ask the user for
        # which screen/window to share.
        pipeline_str = (
            f"pipewiresrc stream-properties=\"properties,media.role=Screen\" ! videoconvert ! videoscale ! videoconvert ! "
            f"video/x-raw,format=RGB,width={width},height={height} ! "
            f"appsink name=sink emit-signals=True max-buffers=1 drop=True"
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.sink = self.pipeline.get_by_name("sink")
        self.sink.connect("new-sample", self._on_new_sample)
        
        # Important: Start a GLib MainLoop in a separate thread.
        # This handles the PipeWire/Portal security handshake background tasks.
        self.loop = GLib.MainLoop()
        self.loop_thread = threading.Thread(target=self.loop.run)
        self.loop_thread.daemon = True
        self.loop_thread.start()

        # Start playing
        res = self.pipeline.set_state(Gst.State.PLAYING)
        if res == Gst.StateChangeReturn.FAILURE:
            # Check for error details on the bus
            bus = self.pipeline.get_bus()
            msg = bus.timed_pop_filtered(Gst.SECOND, Gst.MessageType.ERROR)
            if msg:
                err, debug = msg.parse_error()
                raise RuntimeError(f"GStreamer Error: {err.message}")
            raise RuntimeError("Pipeline failed to play. Check if xdg-desktop-portal is running.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _on_new_sample(self, sink):
        """Callback for when a new frame is ready."""
        sample = sink.emit("pull-sample")
        if sample:
            buf = sample.get_buffer()
            data = buf.extract_dup(0, buf.get_size())
            arr = np.frombuffer(data, dtype=np.uint8)
            self.latest_frame = arr.reshape((self.height, self.width, 3))
        return Gst.FlowReturn.OK

    def get_region_color(self, left, top, right, bottom):
        if self.latest_frame is None:
            return (0, 0, 0)

        y1, y2 = int(top * self.height), int(bottom * self.height)
        x1, x2 = int(left * self.width), int(right * self.width)
        
        region = self.latest_frame[y1:y2, x1:x2]
        if region.size == 0: return (0, 0, 0)
            
        avg = np.mean(region, axis=(0, 1))
        return tuple(avg.astype(int))

    def close(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.loop.quit()

# Test usage
if __name__ == "__main__":
    import time

    with ScreenScanner() as scanner:
        try:
            while True:
                color = scanner.get_region_color(0.4, 0.4, 0.6, 0.6)  # Center 20%
                print(f"\rCenter Color: {color}   ", end="")
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nExiting.")