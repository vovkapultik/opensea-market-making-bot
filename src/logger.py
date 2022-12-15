import logging

from colorlog import ColoredFormatter

log_level = logging.DEBUG
log_format = "%(white)s[%(asctime)s]  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
colors = {
    'WARNING': 'bold_yellow',
    'INFO': 'blue',
    'DEBUG': 'green',
    'ERROR': 'red',
    'CRITICAL': 'bold_red'
}

logging.root.setLevel(log_level)
formatter = ColoredFormatter(fmt=log_format,
                             datefmt="%Y-%m-%d %H:%M:%S",
                             log_colors=colors)

stream = logging.StreamHandler()
stream.setLevel(log_level)
stream.setFormatter(formatter)

log = logging.getLogger('pythonConfig')
log.setLevel(log_level)
log.addHandler(stream)
