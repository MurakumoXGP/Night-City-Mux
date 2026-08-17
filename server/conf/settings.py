from evennia.settings_default import *
import os
from evennia.contrib.base_systems import color_markups

SERVERNAME = "Night City MUSH"
DEBUG = True
SITE_ID = 1

FILE_HELP_ENTRY_MODULES = ["world.help_entries"]

DEFAULT_CMDSETS = ['commands.mycmdset.MyCmdset']

TELNET_ENABLED = True
TELNET_PORTS = [4000]
WEBSERVER_ENABLED = True
WEBSERVER_PORTS = [(4001, 4002)]
SSL_ENABLED = False
SSL_PORTS = [4003]
SSH_ENABLED = False
SSH_PORTS = [4004]
WEBSOCKET_CLIENT_ENABLED = True
WEBSOCKET_CLIENT_PORT = 4005
AMP_PORT = 4006

INSTALLED_APPS += [
    'world.cyberpunk_sheets',
    'world.inventory',
    'world.cyberware',
    'world.factions',
    'world.mail',
    'world.jobs',
    'world.mission_board',
    'world.plots',
    'world.hangouts',
    'world.languages',
    'world.netrunning',
    'world.mystery',
    'world.maker',
    'world.elflines.apps.ElflinesConfig',
]

CMDSET_CHARACTER = "commands.default_cmdsets.CharacterCmdSet"
BASE_ROOM_TYPECLASS = "typeclasses.rooms.Room"
BASE_EXIT_TYPECLASS = "typeclasses.exits.Exit"
BASE_OBJECT_TYPECLASS = "typeclasses.objects.Object"
BASE_CHARACTER_TYPECLASS = "typeclasses.characters.Character"
BASE_ACCOUNT_TYPECLASS = "typeclasses.accounts.Account"
TYPECLASS_PATHS = ["typeclasses"]
TYPECLASS_RELOAD_ON_CHANGE = True
RELOAD_AT_SERVER_STARTSTOP = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(GAME_DIR, 'evennia.db3'),
    }
}

TELNET_INTERFACES = ['0.0.0.0']
WEBSERVER_INTERFACES = ['0.0.0.0']
WEBSOCKET_CLIENT_INTERFACE = '0.0.0.0'

WEBCLIENT_MAX_MESSAGE_LENGTH = 100000
WEBCLIENT_RECONNECT_DELAY = 2000
WEBCLIENT_KEEPALIVE = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '157.245.89.88', 'nightcitymux.com', 'www.nightcitymux.com']

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760
EVENNIA_ADMIN = False

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(GAME_DIR, 'static')
STATICFILES_DIRS = [
    os.path.join(GAME_DIR, "web", "static"),
    os.path.join(GAME_DIR, "wiki", "static"),
    os.path.join(GAME_DIR, "world/jobs/static"),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(GAME_DIR, 'media')

SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 3600 * 24 * 7

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

COLOR_ANSI_EXTRA_MAP = color_markups.MUX_COLOR_ANSI_EXTRA_MAP
COLOR_XTERM256_EXTRA_FG = color_markups.MUX_COLOR_XTERM256_EXTRA_FG
COLOR_XTERM256_EXTRA_BG = color_markups.MUX_COLOR_XTERM256_EXTRA_BG
COLOR_XTERM256_EXTRA_GFG = color_markups.MUX_COLOR_XTERM256_EXTRA_GFG
COLOR_XTERM256_EXTRA_GBG = color_markups.MUX_COLOR_XTERM256_EXTRA_GBG
COLOR_ANSI_XTERM256_BRIGHT_BG_EXTRA_MAP = color_markups.MUX_COLOR_ANSI_XTERM256_BRIGHT_BG_EXTRA_MAP

LOG_DIR = os.path.join(GAME_DIR, "server", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

SERVER_LOG_FILE = os.path.join(LOG_DIR, "server.log")
SERVER_LOG_DAY_ROTATION = 7
SERVER_LOG_MAX_SIZE = 1000000
PORTAL_LOG_FILE = os.path.join(LOG_DIR, "portal.log")
PORTAL_LOG_DAY_ROTATION = 7
PORTAL_LOG_MAX_SIZE = 1000000
HTTP_LOG_FILE = os.path.join(LOG_DIR, "http_requests.log")
LOCKWARNING_LOG_FILE = os.path.join(LOG_DIR, "lockwarnings.log")

try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
CONNECTION_SCREEN_MODULE = "server.conf.connection_screens"
DEFAULT_HOME = "#17"
START_LOCATION = "#17"
