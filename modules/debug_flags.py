'''
Collection of debugging flags to control debugging flow.
'''

# set logging verbosity to DEBUG level
DEBUG_LOGGING = False

# logs skipped frame counts since last frame.
# based on automatically adjusted threshold
SHOW_SKIPPED_FRAMES = True

# logs state changes every scanned frames.
SHOW_STATE_CHANGES = True

# logs marker detection every scanned frames.
SHOW_MARKER_DETECTION = False

# prints state changes summary in a simplified form.
# prints finalized states for video splices.
SHOW_SCANNED_SPLITS = True
