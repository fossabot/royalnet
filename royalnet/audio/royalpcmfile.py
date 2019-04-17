import discord
import ffmpeg
import re
import os
import typing
import logging as _logging
from .youtubedl import YtdlFile, YtdlInfo
from .royalpcmaudio import RoyalPCMAudio

log = _logging.getLogger(__name__)


class RoyalPCMFile(YtdlFile):
    ytdl_args = {
        "logger": log,  # Log messages to a logging.Logger instance.
        "format": "bestaudio"  # Fetch the best audio format available
    }

    def __init__(self, info: "YtdlInfo", **ytdl_args):
        # Preemptively initialize info to be able to generate the filename
        self.info = info
        # Overwrite the new ytdl_args
        self.ytdl_args = {**self.ytdl_args, **ytdl_args}
        log.info(f"Now downloading {info.webpage_url}")
        super().__init__(info, outtmpl=self._ytdl_filename, **self.ytdl_args)
        # Find the audio_filename with a regex (should be video.opus)
        log.info(f"Preparing {self.video_filename}...")
        # Convert the video to pcm
        ffmpeg.input(f"./{self.video_filename}") \
              .output(self.audio_filename, format="s16le", acodec="pcm_s16le", ac=2, ar="48000") \
              .overwrite_output() \
              .run(quiet=not __debug__)
        # Delete the video file
        log.info(f"Deleting {self.video_filename}")
        self.delete_video_file()

    def __repr__(self):
        return f"<RoyalPCMFile {self.audio_filename}>"

    @staticmethod
    def create_from_url(url, **ytdl_args) -> typing.List["RoyalPCMFile"]:
        info_list = YtdlInfo.create_from_url(url)
        return [RoyalPCMFile(info) for info in info_list]

    @property
    def _ytdl_filename(self):
        return f"./downloads/{self.info.title}-{self.info.id}.ytdl"

    @property
    def audio_filename(self):
        return f"./downloads/{self.info.title}-{self.info.id}.pcm"

    def create_audio_source(self):
        return RoyalPCMAudio(self)

    def delete_audio_file(self):
        os.remove(self.audio_filename)