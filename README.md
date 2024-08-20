# OpenCV Video Utils

This project is to assist video-related operation using combined effort of OpenCV and FFMPEG.

## Supported Modules

- Blue Archive

Currently only Blue Archive videos are under the plan for development.

## Command Line

### Confirm Splits

```
perform.py blue-archive cutoff-detect [options...] <files...>
```

#### Debug Options

- `--state-debug`/`--no-state-debug`, forces the switch to skip processing video file
  based on `debug_states.py`. **This toggle is not effective for multiple videos**.
  Also, ignores the toggle if the file does not exists.

### Total Assault Video Combine

```
perform.py blue-archive raid-merge [options...] <files...>
```

#### Options

- `--intro-file <file>`, prepends intro to the video file.
- `-t <files...>`/`--team-overlay <files...>`, team overlay to map with respective video file, based on order.
- `-o <file>`/`--output-file <file>`, video output.

### Joint Firing Drill Video Combine

```
perform.py blue-archive jfd-merge [options...] <files...>
```

#### Options

- `--intro-file <file>`, prepends intro to the video file.
- `-t <files...>`/`--team-overlay <files...>`, team overlay to map with respective video file, based on order.
- `-o <file>`/`--output-file <file>`, video output.
- `--image-pos-top <pixels>`, Y-axis start of image slice.
- `--image-pos-interval <pixels>`, Y-axis offset per slice iteration.
