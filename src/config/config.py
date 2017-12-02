from configparser import ConfigParser
import os

config = ConfigParser()

DEFAULT_CONFIG_FILENAME = 'config.ini'
config_filename = os.getenv('CONFIG_FILENAME', DEFAULT_CONFIG_FILENAME)

full_config_path = os.path.join(os.path.dirname(__file__), config_filename)

config.read(full_config_path)

db_path = config.get('app', 'db_path')
redirect_uri = config.get('app', 'redirect_uri')
state_seperator = config.get('app', 'state_seperator')

spotify_client_id = config.get('spotify', 'client_id')
spotify_client_secret = config.get('spotify', 'client_secret')
spotify_provider = config.get('spotify', 'provider')
spotify_refresh_token_url = config.get('spotify', 'refresh_token_url')
spotify_redirect_uri = config.get('spotify', 'redirect_uri')

youtube_api_service_name = config.get('youtube', 'api_service_name')
youtube_api_version = config.get('youtube', 'api_version')
youtube_api_token_info_url = config.get('youtube', 'api_token_info_url')
youtube_client_id = config.get('youtube', 'client_id')
youtube_client_secret = config.get('youtube', 'client_secret')
youtube_user_agent_string = config.get('youtube', 'user_agent_string')
youtube_state_seperator = config.get('youtube', 'state_seperator')
youtube_redirect_uri = config.get('youtube', 'redirect_uri')
youtube_key = config.get('youtube', 'key')

musixmatch_apikey = config.get('musixmatch', 'apikey')
musixmatch_rooturl = config.get('musixmatch', 'rooturl')

acoustid_apikey = config.get('acoustid', 'apikey')
