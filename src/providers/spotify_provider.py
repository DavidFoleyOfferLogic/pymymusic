import requests
import urllib.parse
import logging
import urllib
import spotipy
import base64
from models import SpotifyAccounts, Songs, UserSongs
import utils
import six
from config import config


client_id = config.spotify_client_id
client_secret = config.spotify_client_secret
provider = config.spotify_provider
refresh_token_url = config.spotify_refresh_token_url
redirect_uri = config.spotify_redirect_uri

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def sync(user):
    logger.info("syncing spotify account")
    spotify_account = SpotifyAccounts.get(SpotifyAccounts.user == user)
    if not is_access_token_valid(spotify_account):
        spotify_refresh_token(spotify_account)
    sp = spotipy.Spotify(auth=spotify_account.access_token)
    auth_user_playlists = sp.current_user_playlists()
    liked_playlist_id = [item['id'] for item in auth_user_playlists['items'] if item['name'] == 'Liked from Radio'][0]
    current_user_id = sp.current_user()['id']
    liked_playlist_tracks = sp.user_playlist_tracks(current_user_id, playlist_id=liked_playlist_id)
    tracks = liked_playlist_tracks['items']
    playlist_songs_tuples = []
    for track in tracks:
        artist_name = track['track']['album']['artists'][0]['name']
        track_name = track['track']['name']
        album_name = track['track']['album']['name']
        playlist_songs_tuples.append((artist_name, track_name, album_name))
    playlist_songs = []
    for song in playlist_songs_tuples:
        playlist_songs.append(
            {
                'artist': song[0],
                'title': song[1],
                'album': song[2]
            }
        )
    nsongs = Songs.sync_songs(playlist_songs)
    UserSongs.sync_songs(nsongs, user)


def build_authorization_header():
    auth_header = base64.b64encode(six.text_type(client_id + ':' + client_secret).encode('ascii'))
    return {'Authorization': 'Basic %s' % auth_header.decode('ascii')}


def is_access_token_valid(spotify_account):
    is_valid = True
    try:
        sp = spotipy.Spotify(spotify_account.access_token)
        sp.current_user_playlists()
    except Exception as ex:
        logger.warn("invalid access token. refreshing")
        is_valid = False
    return is_valid


def spotify_refresh_token(spotify_account):
    """
  request new access token for spotify_account with refresh token
"""
    grant_type = 'refresh_token'
    refresh_token = spotify_account.refresh_token
    payload = {
        'grant_type': grant_type,
        'refresh_token': refresh_token
    }
    authorization_header = build_authorization_header()
    r = requests.post(refresh_token_url, data=payload, headers=authorization_header)
    response_json = r.json()
    logger.debug(f"response json: {response_json}")
    new_access_token = response_json['access_token']
    logger.debug("new access token: " + new_access_token)
    spotify_account.access_token = new_access_token
    spotify_account.save()


def create_spotify_auth_uri(user, redirect_uri):
    """
    Build the oauth url for a user to authenticate with our app with
"""
    spotify_base_auth_url = 'https://accounts.spotify.com/authorize'
    response_type = 'code'
    state_string = utils.build_state_string(user, provider)
    auth_url = build_spotify_auth_url(spotify_base_auth_url, redirect_uri,
                                      client_id, client_secret, response_type,
                                      state_string)
    return auth_url
    webbrowser.open(auth_url, new=0)
    cherrypy.quickstart(OauthHandler())


def build_spotify_auth_url(spotify_base_auth_url, redirect_uri, client_id,
                           client_secret, response_type, state):
    uri_template = "{uri}?redirect_uri={redirect_uri}&client_id={client_id}&client_secret={client_secret}&state={state}&response_type={response_type}&scope={scope}"
    url = uri_template.format(
        uri=spotify_base_auth_url,
        redirect_uri=redirect_uri,
        client_id=client_id,
        client_secret=client_secret,
        response_type=response_type,
        state=state,
        scope=urllib.parse.quote('playlist-read-private', safe='~()*!.\''))
    return url


def auth_and_store_spotify_user(user, code):
    access_token_url = 'https://accounts.spotify.com/api/token'
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    r = requests.post(url=access_token_url, data=data)
    response_json = r.json()
    logger.info(f"response_json: {response_json}")
    access_token = response_json['access_token']
    refresh_token = response_json['refresh_token']
    if access_token:
        SpotifyAccounts.create(
            user=user, access_token=access_token, refresh_token=refresh_token)
    else:
        logger.warn('failed to link spotify account')
