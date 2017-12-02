import youtube_dl
import os
import requests
import logging
from config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

mx_rooturl = config.musixmatch_rooturl
mxmatch_key = config.musixmatch_apikey


def build_track_search_url(page_size=10, page=1, sort_track_rating='desc'):
    track_search_url = f'{mx_rooturl}matcher.tracker.get?q_track={query}&page_size={page_size}&page={page}&s_track_rating={s_track_rating}&apikey={mxmatch_key}'
    return track_search_url


def get_song_metadata_by_title(query):
    page_size = 10
    page = 1
    sort_track_rating = 'desc'
    track_search_url = build_track_search_url(page_size, page, sort_track_rating)
    r = requests.get(track_search_url)
    rjson = r.json()
    message = rjson['message']
    header = message['header']
    num_results = header['available']
    is_results = num_results > 0
    song_json = {}
    if is_results:
        track_list = message['body']['track_list']
        track = track_list[0]['track']
        album_name = track['album_name']
        track_name = track['track_name']
        artist_name = track['artist_name']
        song_json = {
            'artist': artist_name,
            'title': track_name,
            'album': album_name
        }
    else:
        message = f"Song not found on musixmatch: {query}"
        logger.warn(message)
    return song_json


def build_song_full_download_path(download_path, song):
    logger.info("building download_path for song: %s", song)
    artist = song.artist
    name = song.name
    full_path = os.path.expanduser(
        os.path.sep.join([download_path, artist, name]))
    return full_path


def filter_out_already_downloaded_songs(download_path, songs):
    new_songs = []
    # This can definitely be done with a list comp but I think this is more readable
    for song in songs:
        song = song.song
        full_path = build_song_full_download_path(download_path, song)
        full_song_path_with_ext = full_path + '.mp3'
        if not os.path.exists(full_song_path_with_ext):
            new_songs.append(song)
    return new_songs


def download_users_new_songs(user, songs):
    download_dir = user.download_path
    songs = filter_out_already_downloaded_songs(download_dir, songs)
    for song in songs:
        download_song(download_dir, song)


def get_songurl_from_youtube(song):
    youtube_search_url = "https://www.googleapis.com/youtube/v3/search"
    youtube_base_video_url = "https://www.youtube.com/watch?v="
    youtube_key = config.youtube_key
    search_term = " ".join([song.artist, song.name])
    params = {
        "part": "snippet",
        "q": search_term,
        "type": "video",
        "maxResults": 50,
        "key": youtube_key
    }
    r = requests.get(youtube_search_url, params=params)
    response_json = r.json()
    first_match = response_json['items'][0]
    video_id = first_match['id']['videoId']
    youtube_url = youtube_base_video_url + video_id
    return youtube_url


def download_song(download_path, song):
    """
    Download a song using youtube url and song title
    """
    if song.youtube_id is not None:
        youtube_base_video_url = "https://www.youtube.com/watch?v="
        song_url = youtube_base_video_url + song.youtube_id
    else:
        song_url = get_songurl_from_youtube(song)
    song_download_path = build_song_full_download_path(download_path, song)
    download_youtube_video(song_download_path, song_url)


def download_youtube_video(path, videourl):
    outtmpl = path + '.%(ext)s'
    ydl_opts = {
        'format':
        'bestaudio/best',
        'outtmpl':
        outtmpl,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'FFmpegMetadata'
            },
        ],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(videourl, download=True)
