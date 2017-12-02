from peewee import Model, PrimaryKeyField, CharField, ForeignKeyField, DateTimeField, IntegrityError
from playhouse.sqlite_ext import SqliteExtDatabase
import datetime
from gmusicapi import Mobileclient
import logging
import os
from config import config

db_path = os.path.expanduser(config.db_path)
db = SqliteExtDatabase(db_path)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def create_tables():
    tables = [Songs, GoogleAccounts, GoogleMusicPlayerAccounts, SpotifyAccounts, User, UserSongs]
    db.create_tables(tables, safe=True)


def drop_table(table):
    db.drop_table(table)


def drop_tables():
    tables = [GoogleAccounts, GoogleMusicPlayerAccounts, SpotifyAccounts, User, UserSongs]
    db.drop_tables(tables)


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    id = PrimaryKeyField()
    username = CharField(unique=True)
    password = CharField()
    download_path = CharField()
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)


# This account requires an app password
class GoogleMusicPlayerAccounts(BaseModel):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, related_name='google_music_account')
    username = CharField(unique=True)
    password = CharField()
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def sync(self):
        self.google_music_login()
        songs = self.get_liked_songs()
        # these songs are our db model instances, we need these to pull the id to insert in the UserSongs table
        nsongs = Songs.sync_songs(songs)
        user = self.user
        UserSongs.sync_songs(nsongs, user)

    def google_music_login(self):
        logger.debug("logging in user: {0}".format(self.username))
        self._api = Mobileclient()
        self._api.login(self.username, self.password,
                        Mobileclient.FROM_MAC_ADDRESS)

    def get_playlists_songs(self):
        playlists = self._api.get_all_user_playlist_contents()
        return playlists

    def get_liked_songs(self):
        liked_songs = self._api.get_promoted_songs()
        logger.info(f"liked_songs: {liked_songs}")
        return liked_songs

    def get_all_songs(self):
        return self._api.get_all_songs()


class GoogleAccounts(BaseModel):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, related_name='google_account')
    access_token = CharField(unique=True)
    refresh_token = CharField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)


class SpotifyAccounts(BaseModel):
    """Model for spotify accounts oauth tokens

    """

    id = PrimaryKeyField()
    user = ForeignKeyField(User, related_name='spotify_account')
    access_token = CharField(unique=True)
    refresh_token = CharField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)


class Songs(BaseModel):
    """Documentation for Songs

    """
    # TODO: should I add a source field here? I think I should if only because it helps
    # with my youtube problem
    id = PrimaryKeyField()
    name = CharField()
    artist = CharField()
    album = CharField(null=True)
    youtube_id = CharField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        indexes = (
            # create a unique on from/to/date
            ((
                'name',
                'artist', ), True), )

    @staticmethod
    def sync_songs(songs):
        nsongs = []
        for song in songs:
            logger.info("adding or updating song with songs db: %s", song)

            artist = song['artist']
            name = song['title']
            album = song['album']
            videoid = None
            if 'videoid' in song:
                videoid = song['videoid']
            song = Songs.get_or_create(name=name,
                                       artist=artist,
                                       album=album, youtube_id=videoid, defaults={})
            nsongs.append(song)
        return nsongs


class UserSongs(BaseModel):
    id = PrimaryKeyField()
    user = ForeignKeyField(User, related_name='songs')
    song = ForeignKeyField(Songs, related_name='users')
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    @staticmethod
    def sync_songs(songs, user):
        user_id = user.id
        for song in songs:
            song_id = song[0].id
            logger.debug("creating user song entry for user: %s and song: %s", user_id, song_id)
            try:
                UserSongs.create(user=user_id, song=song_id)
            except IntegrityError:
                pass
            except Exception as ex:
                logger.error("error creating usersong", ex)


    @staticmethod
    def get_users_songs(user):
        usersongs = UserSongs.select().where(UserSongs.user == user)
        return usersongs

    class Meta:
        indexes = (
            # create a unique on from/to/date
            ((
                'user',
                'song', ), True), )
