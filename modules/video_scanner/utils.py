import numpy as np
import cv2 as cv

def calculate_similarity(previous_frame, current_frame) -> float:
  '''
  Calculates similarity between two frames.
  '''
  difference = cv.absdiff(current_frame, previous_frame)
  difference = cv.cvtColor(difference, cv.COLOR_BGR2GRAY)
  score = cv.calcHist([difference], [0], None, [4], [0, 256])
  score = 100 * score / score.sum()

  return score[0]

def slice_to_pixels(frame, coord : tuple[slice, slice]) -> tuple[slice, slice]:
  '''
  Converts given coordinate slice into pixels.

  Absolute References:
    slice(m:int,   n:int)   -> slice(m, n)
    slice(m:int,   n:float) -> slice(m, (s - m) * n)
    slice(m:float, n:float) -> slice(s * m, (s - (s * m)) * n)

  Relative References:
    slice(m:float, n:int)   -> slice(s * m, s * m + n)
  '''
  def translate_slice(size, point):
    start, stop = point.start, point.stop
    base_start, base_stop = start, stop

    if base_start is None:
      start = 0
    elif isinstance(base_start, float):
      start = int(size * start)

    if isinstance(base_stop, float):
      stop = start + int((size - start) * stop)
    elif isinstance(base_stop, int):
      if isinstance(base_start, int):
        # don't do anything
        pass
      elif isinstance(base_start, float):
        # relative point
        stop = start + stop

    # revert after temporary hack for stop anchor reference
    if base_start is None:
      start = base_start

    return slice(start, stop)

  frame_shape = frame.shape[-2::-1]
  return tuple(
    translate_slice(size, point)
    for point, size in zip(coord, frame_shape)
  )

def calculate_detection_threshold(frame, marker) -> float:
  '''
  Calculates detection threshold based on marker dimensions.

  The bigger the image the lower the matching threshold required.
  Starts from 32 to 256, for each length.
  End value ranges from 96% to 80%.
  '''
  width, height = [max(24, size) for size in (marker.width, marker.height)]
  rate_width, rate_height = [
    ((max(32, min(256, adjusted_size)) - 32) / 224)
    for adjusted_size in (width, height)
  ]

  return 0.96 - 0.16 * ((rate_width + rate_height) / 2) ** 2.5

def calculate_similarity_threshold(scanner, start_threshold : float, reduce_threshold : float = 0.05) -> float:
  '''
  Calculates adjusted similarity threshold between frames.

  Adjusted Similarity Threshold calculated through
  several factors of Scanner state.
  Values are determined through several factors such as:
  - Consecutive skips of frames
  - Average frame skipped
  '''
  def contiguous_count(ary):
    count, max_count = 0, 0
    for valid in ary:
      count = count + 1 if valid else 0
      max_count = max(count, max_count)

    return max_count

  if len(scanner.skip_history) <= max(5, (scanner.skip_history.maxlen or 0) // 10):
    return start_threshold

  criterion_threshold = max(5, int(scanner.skip_history.maxlen * 0.4))
  skip_array = np.array(scanner.skip_history)
  calculated_average = skip_array.mean() ** 0.5
  contiguous_rate = contiguous_count(
    (
      (skip_array > 0) &
      (skip_array < max(1, calculated_average))
    ),
  )
  ave_nerf_rate = 1 - 0.5 * min(1, max(0, contiguous_rate - 5) / criterion_threshold)
  skip_array = skip_array[skip_array > 0]
  criterion_count = np.count_nonzero(
    (skip_array > 0) &
    (skip_array < max(1, ave_nerf_rate * skip_array.mean() ** 0.5)),
  )
  criterion_count = min(criterion_threshold, max(0, criterion_count - 5))
  threshold_rate = 1.0 - reduce_threshold * ((criterion_count / criterion_threshold) ** 1.5)

  return start_threshold * threshold_rate
