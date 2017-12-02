import httplib2
import requests
import logging
import os
import acoustid
from oauth2client import client
from oauth2client.client import AccessTokenCredentials
from apiclient.discovery import build
from models import Songs, UserSongs, GoogleAccounts
from config import config
import music_util

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

YOUTUBE_API_SERVICE_NAME = config.youtube_api_service_name
YOUTUBE_API_VERSION = config.youtube_api_version
GOOGLE_API_TOKEN_INFO_URL = config.youtube_api_token_info_url
GOOGLE_CLIENT_ID = config.youtube_client_id
GOOGLE_CLIENT_SECRET = config.youtube_client_secret
user_agent_string = config.youtube_user_agent_string
state_seperator = config.youtube_state_seperator
redirect_uri = config.youtube_redirect_uri

acoustid_apikey = config.acoustid_apikey


def build_youtube_video_url(videoid):
    video_url = f'https://www.youtube.com/watch?v={videoid}'
    return video_url


def create_youtube_auth_uri(user, redirect_uri):
    state_string = "{0}{1}{2}{3}{4}".format(user.username, state_seperator,
                                            user.password, state_seperator,
                                            "youtube")
    flow = client.flow_from_clientsecrets(
        'client_secrets.json',
        scope='https://www.googleapis.com/auth/youtube.force-ssl',
        redirect_uri=redirect_uri)
    flow.params['access_type'] = 'offline'  # offline access
    flow.params['approval_prompt'] = 'force'  # offline access
    flow.params['include_granted_scopes'] = 'true'  # incremental auth
    flow.params['state'] = state_string
    auth_uri = flow.step1_get_authorize_url()
    return auth_uri


def auth_and_store_google_user(user, code, scope):
    flow = client.flow_from_clientsecrets(
        'client_secrets.json',
        scope='https://www.googleapis.com/auth/youtube.force-ssl',
        redirect_uri=redirect_uri)
    credentials = flow.step2_exchange(code)
    import httplib2
    http_auth = credentials.authorize(httplib2.Http())
    access_token = credentials.access_token
    refresh_token = credentials.refresh_token
    if access_token:
        GoogleAccounts.create(
            user=user, access_token=access_token, refresh_token=refresh_token)
    else:
        logger.warn("Failed to link google account")


def is_valid_access_token(access_token):
    valid_token_url = GOOGLE_API_TOKEN_INFO_URL.format(
        access_token=access_token)
    r = requests.get(valid_token_url)
    response_json = r.json()


def refresh_access_token(refresh_token):
    refresh_token_url = 'https://www.googleapis.com/oauth2/v4/token'
    grant_type = 'refresh_token'
    payload = {
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'refresh_token': refresh_token,
        'grant_type': grant_type
    }
    headers = {'Content-type': 'application/x-www-form-urlencoded'}
    r = requests.post(refresh_token_url, headers=headers, data=payload)
    response_json = r.json()
    new_access_token = response_json['access_token']
    return new_access_token


def sync(user):
    """Sync user's music videos.
    The flow here is different than every other provider because
    youtube isn't a music streaming provider
    so we don't get any metadata about the songs.

    :param user: the user
    :returns:
    :rtype:

    """
    google_account = GoogleAccounts.get(GoogleAccounts.user == user)
    if not is_valid_access_token(google_account.access_token):
        new_access_token = refresh_access_token(google_account.refresh_token)
        google_account.access_token = new_access_token
        google_account.save()
    credentials = AccessTokenCredentials(
        google_account.access_token, user_agent=user_agent_string)
    youtube = build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        http=credentials.authorize(httplib2.Http()))
    # TODO: The playlist should be set by the user
    target_playlist = 'Music Videos'
    playlists = youtube.playlists().list(
        part='contentDetails, snippet', mine=True).execute()
    items = playlists['items']
    for playlist in items:
        if playlist['snippet']['title'] == target_playlist:
            playlist_id = playlist['id']
    nextPageToken = None
    playlist_songs = []
    while True:
        if nextPageToken is not None:
            playlist_items_response = youtube.playlistItems().list(
                part='snippet,contentDetails', playlistId=playlist_id, maxResults=50, pageToken=nextPageToken).execute()
        else:
            playlist_items_response = youtube.playlistItems().list(
                part='snippet,contentDetails', playlistId=playlist_id, maxResults=50).execute()
        playlists = playlist_items_response['items']
        for song in playlists:
            videoid = song['contentDetails']['videoId']
            is_new_song = len(Songs.select().where(Songs.youtube_id == videoid)) == 0
            if is_new_song:
                videourl = build_youtube_video_url(videoid)
                title = song['snippet']['title']
                download_path = build_youtube_temp_download_path(user.download_path, title)
                # TODO: What to return here? Maybe nothing and just try-catch? Not sure
                music_util.download_youtube_video(download_path, videourl)
                destfile = download_path + '.mp3'  # Need to add this because youtube-dl does
                song = run_acoustic_analysis_on_music_video(destfile)
                if song is None:
                    song = prompt_user_for_music_video_song_metadata()
                song['videoid'] = videoid
                playlist_songs.append(song)
                move_downloaded_youtube_song_to_correct_path(user, song, destfile)
        if 'nextPageToken' not in playlist_items_response or playlist_items_response['nextPageToken'].strip() == '':
            break
        else:
            nextPageToken = playlist_items_response['nextPageToken']
    nsongs = Songs.sync_songs(playlist_songs)
    UserSongs.sync_songs(nsongs, user)


def build_youtube_temp_download_path(user_download_path, title):
    """Build the download path for a youtube video

    :param user_download_path: User's configured path to download music to
    :param title: Title of the youtube video being downloaded
    :returns:
    :rtype:

    """
    temp_path = os.path.expanduser(
        os.path.sep.join([user_download_path, 'untagged_youtube_songs', title]))
    return temp_path


def run_acoustic_analysis_on_music_video(music_file):
    """FIXME! briefly describe function

    :param music_file:
    :returns: Song if available otherwise None
    :rtype:

    """
    song = None
    # FIXME:
    album = None
    for score, recording_id, title, artist in acoustid.match(apikey, music_file):
        song = {
            'artist': artist,
            'title': title,
            'album': album
        }
        break  # Only keep the first result... yea yea I know
    return song


def prompt_user_for_music_video_song_metadata():
    print("Unable to find metadata for youtube music video song. Please help by entering it here")
    title = input("Please enter the song's name: ")
    artist = input("Please enter the song's artist: ")
    album = input("Please enter the song's album: ")
    song = {
        'artist': artist,
        'title': title,
        'album': album
    }
    return song


def move_downloaded_youtube_song_to_correct_path(user, song, temp_download_path):
    """Move the downloaded music video to the correct download path based on the
artist and song name that we retrieved with acoustics or the user entered. We don't want to
download the song twice and at worst chance getting the wrong song.

    :param user: The user
    :param song: The song
    :param temp_download_path: The current, temp path of the downloaded song
    :returns:
    :rtype:
    """
    nsong = Songs(name=song['title'], artist=song['artist'], album=song['album'])
    correct_download_path = music_util.build_song_full_download_path(user.download_path, nsong)
    correct_download_path += '.mp3'
    safe_rename_file(temp_download_path, correct_download_path)


def safe_rename_file(oldpath, newpath):
    success = True
    try:
        new_path_basedir = os.path.dirname(newpath)
        if not os.path.exists(new_path_basedir):
            os.makedirs(new_path_basedir)
        os.rename(oldpath, newpath)
    except Exception as ex:
        logger.error('failed to move youtube music video to correct download directory', ex)
        success = False
    return success
