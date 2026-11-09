"""A widget to play video files (Sixel, or half blocks when Sixel isn't available).

Decoding uses PyAV, audio output uses sounddevice. The audio is the master
clock; when the terminal can't keep up, late frames are dropped so that video
stays in sync with the audio.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from textual import log
from textual._graphics import Fit, RenderMode, contain_size
from textual._graphics_widget import MEDIA_INSTALL_HINT, GraphicsWidget
from textual.binding import Binding, BindingType
from textual.geometry import Region, Size
from textual.message import Message
from textual.reactive import var

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

SEEK_STEP = 5.0
"""Seconds to seek with the left / right keys."""


class _Clock:
    """Playback clock: wall time, re-anchored by the audio output when there is audio."""

    def __init__(self, position: float) -> None:
        self._origin = perf_counter() - position
        self.started = threading.Event()

    def time(self) -> float:
        return perf_counter() - self._origin

    def sync(self, position: float) -> None:
        """Set the current position (called by the audio output)."""
        self._origin = perf_counter() - position
        self.started.set()

    def start(self, position: float) -> None:
        if not self.started.is_set():
            self.sync(position)


@dataclass
class _Target:
    """What the decoder should produce (set by the widget, read by the decoder thread)."""

    content_size: Size
    cell_size: Size
    fit: Fit
    background: tuple[int, int, int]
    sixel: bool
    colors: int

    @property
    def pixel_size(self) -> tuple[int, int]:
        width, height = self.content_size
        if self.sixel:
            return (width * self.cell_size.width, height * self.cell_size.height)
        return (width, height * 2)


@dataclass
class _Frame:
    image: PILImage
    time: float
    target: _Target
    sixel: str | None


def _convert_frame(frame: Any, target: _Target) -> PILImage:
    """Scale a PyAV video frame to the target (with swscale, which is fast)."""
    from PIL import Image

    target_width, target_height = target.pixel_size
    width, height = frame.width, frame.height
    if target.fit == "fill":
        return frame.to_image(width=target_width, height=target_height)
    if target.fit == "cover":
        scale = max(target_width / width, target_height / height)
        scaled_width = max(target_width, round(width * scale))
        scaled_height = max(target_height, round(height * scale))
        image = frame.to_image(width=scaled_width, height=scaled_height)
        left = (scaled_width - target_width) // 2
        top = (scaled_height - target_height) // 2
        return image.crop((left, top, left + target_width, top + target_height))
    scaled_width, scaled_height = contain_size((width, height), (target_width, target_height))
    image = frame.to_image(width=scaled_width, height=scaled_height)
    if image.size == (target_width, target_height):
        return image
    canvas = Image.new("RGB", (target_width, target_height), target.background)
    canvas.paste(
        image, ((target_width - scaled_width) // 2, (target_height - scaled_height) // 2)
    )
    return canvas


class _AudioOutput:
    """Decodes the audio track and plays it with sounddevice, driving the clock."""

    def __init__(
        self, path: str, position: float, clock: _Clock, muted: Callable[[], bool]
    ) -> None:
        import av
        import sounddevice

        self._clock = clock
        self._muted = muted
        self._stop = threading.Event()
        self._container = av.open(path)
        self._stream = self._container.streams.audio[0]
        self._rate = self._stream.rate or 48000
        self._channels = 2 if (self._stream.channels or 2) >= 2 else 1
        self._position = position
        self._buffer: deque[tuple[float, Any]] = deque()
        self._buffered = 0
        self._condition = threading.Condition()
        self._finished = False
        self._thread = threading.Thread(
            target=self._decode, name="textual-video-audio", daemon=True
        )
        self._output = sounddevice.OutputStream(
            samplerate=self._rate,
            channels=self._channels,
            dtype="float32",
            callback=self._callback,
            latency="low",
        )

    def start(self) -> None:
        self._thread.start()
        self._output.start()

    def stop(self) -> None:
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        try:
            self._output.stop()
            self._output.close()
        except Exception:
            pass
        self._thread.join(timeout=2)
        try:
            self._container.close()
        except Exception:
            pass

    def _decode(self) -> None:
        import av
        import numpy as np

        position = self._position
        resampler = av.AudioResampler(
            format="flt", layout="stereo" if self._channels == 2 else "mono", rate=self._rate
        )
        try:
            if position > 0:
                self._container.seek(int(position * av.time_base), backward=True)
            for frame in self._container.decode(self._stream):
                if self._stop.is_set():
                    return
                frame_time = frame.time
                for resampled in resampler.resample(frame):
                    samples = resampled.to_ndarray().reshape(-1, self._channels)
                    start = position if frame_time is None else frame_time
                    if frame_time is not None and frame_time < position:
                        skip = int((position - frame_time) * self._rate)
                        samples = samples[skip:]
                        start = position
                    if not len(samples):
                        continue
                    samples = np.ascontiguousarray(samples, dtype=np.float32)
                    with self._condition:
                        # Keep about one second buffered
                        while self._buffered > self._rate and not self._stop.is_set():
                            self._condition.wait(0.1)
                        self._buffer.append((start, samples))
                        self._buffered += len(samples)
        except Exception as error:
            log.error(f"Video audio decode failed: {error}")
        finally:
            self._finished = True

    def _callback(self, output, frame_count, time_info, status) -> None:
        written = 0
        current: float | None = None
        with self._condition:
            while written < frame_count and self._buffer:
                start, samples = self._buffer[0]
                count = min(frame_count - written, len(samples))
                output[written : written + count] = samples[:count]
                if current is None:
                    current = start
                written += count
                if count == len(samples):
                    self._buffer.popleft()
                else:
                    self._buffer[0] = (start + count / self._rate, samples[count:])
                self._buffered -= count
            self._condition.notify_all()
        if written < frame_count:
            output[written:] = 0
        if self._muted():
            output[:] = 0
        if current is not None:
            latency = self._output.latency if isinstance(self._output.latency, float) else 0.0
            self._clock.sync(max(0.0, current - latency))


class _Decoder:
    """Decodes video frames in a thread and delivers them on time."""

    def __init__(
        self,
        path: str,
        position: float,
        clock: _Clock,
        get_target: Callable[[], _Target | None],
        deliver: Callable[[_Frame], None],
        on_end: Callable[[], None],
        max_fps: float | None,
        single_frame: bool = False,
    ) -> None:
        self._path = path
        self._position = position
        self._clock = clock
        self._get_target = get_target
        self._deliver = deliver
        self._on_end = on_end
        self._min_interval = 1 / max_fps if max_fps else 0.0
        self._single_frame = single_frame
        self.dropped = 0
        """Frames dropped because they were late."""
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="textual-video-decoder", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=2)

    def _render(self, frame: Any, time: float) -> _Frame | None:
        from textual._sixel import encode_sixel

        target = self._get_target()
        if target is None or not target.content_size.area:
            return None
        image = _convert_frame(frame, target)
        sixel = encode_sixel(image, target.colors, fast=True) if target.sixel else None
        return _Frame(image, time, target, sixel)

    def _run(self) -> None:
        import av

        try:
            container = av.open(self._path)
        except Exception as error:
            log.error(f"Unable to open video: {error}")
            return
        stop = self._stop
        clock = self._clock
        position = self._position
        try:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            rate = float(stream.average_rate or 30)
            frame_duration = 1 / rate if rate > 0 else 1 / 30
            if position > 0:
                container.seek(int(position / stream.time_base), stream=stream, backward=True)
            last_shown: float | None = None
            for frame in container.decode(stream):
                if stop.is_set():
                    return
                time = frame.time
                if time is None:
                    continue
                if time < position - frame_duration / 2:
                    continue  # Decoding up to the seek position
                if self._single_frame:
                    rendered = self._render(frame, time)
                    if rendered is not None:
                        self._deliver(rendered)
                    return

                if last_shown is None:
                    clock.start(time)
                    clock.started.wait(1.0)  # Give the audio a moment to start
                else:
                    if self._min_interval and time - last_shown < self._min_interval:
                        continue
                    # Wait until the frame is due
                    while not stop.is_set():
                        delay = time - clock.time()
                        if delay <= 0:
                            break
                        stop.wait(min(delay, 0.05))
                    if stop.is_set():
                        return
                    # Too late? Drop it (the next frame will be closer to the clock)
                    if clock.time() - time > frame_duration:
                        self.dropped += 1
                        continue

                rendered = self._render(frame, time)
                if rendered is None:
                    continue
                last_shown = time
                if stop.is_set():
                    return
                self._deliver(rendered)
            if not stop.is_set():
                self._on_end()
        except Exception as error:
            log.error(f"Video decode failed: {error}")
        finally:
            container.close()


class Video(GraphicsWidget, can_focus=True):
    """Plays a video file, with audio.

    Uses Sixel when the terminal supports it, and colored half blocks otherwise.
    Requires PyAV, Pillow, NumPy, and sounddevice for audio
    (`pip install textual[media]`).
    """

    DEFAULT_CSS = """
    Video {
        width: auto;
        height: auto;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle", "Play/Pause"),
        Binding("left", "seek(-5)", "Back", show=False),
        Binding("right", "seek(5)", "Forward", show=False),
        Binding("m", "toggle_mute", "Mute"),
    ]

    position: var[float] = var(0.0)
    """Current position in seconds."""
    duration: var[float] = var(0.0)
    """Duration in seconds (0 if unknown)."""
    playing: var[bool] = var(False)
    """Is the video playing?"""
    muted: var[bool] = var(False)
    """Is the audio muted?"""

    class Started(Message):
        """Posted when playback starts."""

        def __init__(self, video: Video) -> None:
            super().__init__()
            self.video = video

        @property
        def control(self) -> Video:
            return self.video

    class Paused(Started):
        """Posted when playback is paused."""

    class Finished(Started):
        """Posted when the video reaches the end (and isn't looping)."""

    def __init__(
        self,
        source: str | Path,
        *,
        autoplay: bool = False,
        loop: bool = False,
        audio: bool = True,
        max_fps: float | None = None,
        fit: Fit = "contain",
        render_mode: RenderMode = "auto",
        colors: int = 128,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """
        Args:
            source: Path (or URL supported by FFmpeg) of the video.
            autoplay: Start playing when mounted.
            loop: Restart at the end.
            audio: Play the audio track (requires sounddevice).
            max_fps: Maximum frames per second to display (`None` for the video rate).
            fit: How frames are scaled: "contain", "cover", or "fill".
            render_mode: "auto" (Sixel if supported), "sixel", or "halfblock".
            colors: Maximum number of colors per Sixel frame (fewer is faster).
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes of the widget.
            disabled: Whether the widget is disabled or not.
        """
        super().__init__(
            fit=fit,
            render_mode=render_mode,
            colors=colors,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.source = str(source)
        self.autoplay = autoplay
        self.loop = loop
        self.audio = audio
        self.max_fps = max_fps
        self._natural_size: tuple[int, int] | None = None
        self._has_audio = False
        self._frame: _Frame | None = None
        self._target: _Target | None = None
        self._decoder: _Decoder | None = None
        self._audio_output: _AudioOutput | None = None
        self._clock: _Clock | None = None
        self.frames_shown = 0
        self._pending_frame: _Frame | None = None
        self._pending_lock = threading.Lock()
        """Number of frames displayed since the widget was created."""
        self._frames_dropped = 0

    # -- Public API ---------------------------------------------------------

    def play(self) -> None:
        """Start (or resume) playback."""
        if self.playing or self._graphics_error is not None:
            return
        if self.duration and self.position >= self.duration - 0.05:
            self.position = 0.0
        self._start(self.position)
        self.playing = True
        self.post_message(self.Started(self))

    def pause(self) -> None:
        """Pause playback."""
        if not self.playing:
            return
        if self._clock is not None:
            self.position = max(0.0, self._clock.time())
        self._stop_playback()
        self.playing = False
        self.post_message(self.Paused(self))

    def toggle(self) -> None:
        """Play if paused, pause if playing."""
        if self.playing:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        """Stop playback and go back to the start."""
        self.pause()
        self.seek(0)

    def seek(self, position: float) -> None:
        """Go to a position.

        Args:
            position: Position in seconds.
        """
        position = max(0.0, position)
        if self.duration:
            position = min(position, max(0.0, self.duration - 0.1))
        self.position = position
        if self.playing:
            self._stop_playback()
            self._start(position)
        else:
            self._show_still(position)

    # -- Actions ------------------------------------------------------------

    def action_toggle(self) -> None:
        self.toggle()

    def action_seek(self, offset: float) -> None:
        current = self._clock.time() if (self.playing and self._clock) else self.position
        self.seek(current + offset)

    def action_toggle_mute(self) -> None:
        self.muted = not self.muted

    # -- Internals ----------------------------------------------------------

    def on_mount(self) -> None:
        try:
            import av
        except ImportError:
            self.set_graphics_error(f"Video requires PyAV: {MEDIA_INSTALL_HINT}")
            return
        try:
            with av.open(self.source) as container:
                stream = container.streams.video[0]
                width, height = stream.codec_context.width, stream.codec_context.height
                aspect = stream.sample_aspect_ratio
                if aspect:
                    width = round(width * float(aspect))
                self._natural_size = (width, height)
                if container.duration:
                    self.duration = container.duration / av.time_base
                elif stream.duration and stream.time_base:
                    self.duration = float(stream.duration * stream.time_base)
                self._has_audio = bool(container.streams.audio)
        except Exception as error:
            self.set_graphics_error(f"Unable to open video: {error}")
            return
        self.graphics_changed(layout=True)
        self.call_after_refresh(self._after_first_layout)

    def _after_first_layout(self) -> None:
        self._update_target()
        if self.autoplay:
            self.play()
        else:
            self._show_still(0.0)

    def on_unmount(self) -> None:
        self._stop_playback()

    def on_resize(self) -> None:
        self._update_target()

    def graphics_changed(self, layout: bool = False) -> None:
        super().graphics_changed(layout=layout)
        if self.is_mounted:
            self._update_target()

    def _update_target(self) -> None:
        if not self.is_mounted:
            return
        self._target = _Target(
            content_size=self.size,
            cell_size=self._cell_size,
            fit=self.fit,
            background=self._background_rgb,
            sixel=self.uses_sixel,
            colors=self.sixel_colors,
        )
        if not self.playing and self._natural_size is not None and self._frame is not None:
            if self._frame.target != self._target:
                self._show_still(self.position)

    def _get_target(self) -> _Target | None:
        return self._target

    def _start(self, position: float) -> None:
        self._stop_playback()
        clock = self._clock = _Clock(position)
        if self.audio and self._has_audio:
            try:
                self._audio_output = _AudioOutput(
                    self.source, position, clock, lambda: self.muted
                )
                self._audio_output.start()
            except ImportError:
                log.warning(f"Video audio requires sounddevice: {MEDIA_INSTALL_HINT}")
                self._audio_output = None
            except Exception as error:
                log.error(f"Unable to play audio: {error}")
                self._audio_output = None
        self._decoder = _Decoder(
            self.source,
            position,
            clock,
            self._get_target,
            self._deliver_from_thread,
            self._end_from_thread,
            self.max_fps,
        )
        self._decoder.start()

    @property
    def frames_dropped(self) -> int:
        """Number of frames dropped because they were late (the terminal couldn't keep up)."""
        current = self._decoder.dropped if self._decoder is not None else 0
        return self._frames_dropped + current

    def _stop_playback(self) -> None:
        if self._decoder is not None:
            self._frames_dropped += self._decoder.dropped
            self._decoder.stop()
            self._decoder = None
        if self._audio_output is not None:
            self._audio_output.stop()
            self._audio_output = None

    def _show_still(self, position: float) -> None:
        """Show a single frame (when not playing)."""
        if self._decoder is not None:
            self._decoder.stop()
        self._decoder = _Decoder(
            self.source,
            position,
            _Clock(position),
            self._get_target,
            self._deliver_from_thread,
            lambda: None,
            None,
            single_frame=True,
        )
        self._decoder.start()

    def _deliver_from_thread(self, frame: _Frame) -> None:
        """Hand a frame to the app thread without waiting.

        Only the most recent frame is kept: if the app hasn't shown the previous
        frame yet, it is replaced (dropped), so decoding never waits for the terminal.
        """
        with self._pending_lock:
            replaced = self._pending_frame is not None
            self._pending_frame = frame
        if replaced:
            if self._decoder is not None:
                self._decoder.dropped += 1
            return
        loop = self.app._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._present_pending)
        except RuntimeError:
            pass  # Loop closed

    def _present_pending(self) -> None:
        with self._pending_lock:
            frame = self._pending_frame
            self._pending_frame = None
        if frame is not None:
            self._present(frame)

    def _end_from_thread(self) -> None:
        # Must not wait: `_on_end` may stop (and join) the calling decoder thread.
        loop = self.app._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._on_end)
        except RuntimeError:
            pass  # Loop closed

    def _present(self, frame: _Frame) -> None:
        """Show a decoded frame (on the app thread)."""
        if not self.is_mounted:
            return
        self._frame = frame
        if self.playing:
            self.position = frame.time
            self.frames_shown += 1
        super().graphics_changed()
        target = self._target
        if frame.sixel is not None and target is not None and frame.target == target:
            content_size = target.content_size
            key = self._sixel_key(content_size, Region(0, 0, *content_size))
            self._sixel_cache[key] = frame.sixel

    def _on_end(self) -> None:
        if not self.playing:
            return
        if self.loop:
            self._start(0.0)
            return
        self._stop_playback()
        self.playing = False
        if self.duration:
            self.position = self.duration
        self.post_message(self.Finished(self))

    def get_frame(self) -> PILImage | None:
        return None if self._frame is None else self._frame.image

    def get_frame_size(self) -> tuple[int, int] | None:
        return self._natural_size

    def _scaled_frame(self, size: tuple[int, int]) -> PILImage | None:
        frame = self.get_frame()
        if frame is not None and frame.size == size:
            return frame
        return super()._scaled_frame(size)
