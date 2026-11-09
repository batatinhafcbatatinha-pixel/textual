"""Generate a short sample video with audio (sample.mp4) for the media demo."""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np

path = Path(__file__).parent / "sample.mp4"
width, height, fps, seconds = 320, 180, 30, 4
rate = 44100

with av.open(str(path), "w") as container:
    video = container.add_stream("libx264", rate=fps)
    video.width, video.height, video.pix_fmt = width, height, "yuv420p"
    audio = container.add_stream("aac", rate=rate)
    audio.layout = "stereo"

    y, x = np.mgrid[0:height, 0:width]
    for index in range(fps * seconds):
        t = index / fps
        frame = np.zeros((height, width, 3), np.uint8)
        frame[..., 0] = (np.sin(x / 30 + t * 3) * 0.5 + 0.5) * 255
        frame[..., 1] = (np.cos(y / 25 + t * 2) * 0.5 + 0.5) * 255
        frame[..., 2] = 120
        cx = int((t / seconds) * (width - 40)) + 20
        frame[height // 2 - 20 : height // 2 + 20, cx - 20 : cx + 20] = 255
        for packet in video.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")):
            container.mux(packet)
    for packet in video.encode():
        container.mux(packet)

    samples_per_frame = 1024
    total = rate * seconds
    for start in range(0, total, samples_per_frame):
        t = (np.arange(start, min(total, start + samples_per_frame)) / rate)
        tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        data = np.stack([tone, tone])
        frame = av.AudioFrame.from_ndarray(data, format="fltp", layout="stereo")
        frame.sample_rate = rate
        frame.pts = start
        frame.time_base = Fraction(1, rate)
        for packet in audio.encode(frame):
            container.mux(packet)
    for packet in audio.encode():
        container.mux(packet)
print(path)
