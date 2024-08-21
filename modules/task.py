from typing import Any # noqa: F401

import cv2 as cv # noqa: F401

import modules.video_ops as ops
from modules.video_scanner import task as scanner_task

def scan_video_timing(video_file : str):
  opts = {}
  # opts['seek_option'] = (cv.CAP_PROP_POS_FRAMES, 13500)
  with scanner_task.Scanner(video_file, **opts) as (scanner, video):
    for scan_state in scanner:
      scan_state.process()
  # print(scanner.state_logs)

  return scanner.state_logs

def create_filter_script_raid(
  output_file : str,
  intro_file : str | None,
  video_files : list[str],
  image_files : list[str],
  video_splits,
):
  with ops.ffmpeg.VideoTransform(
    video_files = video_files,
    image_files = image_files,
    splits      = video_splits,
    output_file = output_file,
  ) as tf:
    tf.options['image_crop'] = False

def create_filter_script_jfd(
  output_file : str,
  intro_file : str | None,
  video_files : list[str],
  image_file : str | None,
  video_splits,
  jfd_options : object,
):
  with ops.ffmpeg.VideoTransform(
    video_files = video_files,
    image_files = [image_file],
    splits      = video_splits,
    output_file = output_file,
  ) as tf:
    tf.options['image_crop'] = True
    tf.options['image_crop_width'] = 1392
    tf.options['image_crop_height'] = 135
    tf.options['image_crop_start'] = jfd_options.crop_top
    tf.options['image_crop_interval'] = jfd_options.crop_interval
