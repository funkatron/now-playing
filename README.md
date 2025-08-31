# Dead Agent "Now Playing" Scripts

This repository contains scripts to retrieve and display the currently playing song from Apple Music and the Spotify desktop app on macOS.

# Requirements

- MacOS 10.13 or above (not tested on earlier versions)
- Python 3.9 or above
- git

# Installation

1. Clone the repository using git:
    ```bash
    git clone
    ```

2. Create a virtual environment in the repository root using the following command:
    ```bash
    python3 -m venv venv
    ```

3. Activate the virtual environment using the following command:
    ```bash
    source venv/bin/activate
    ```

4. Install the required packages using pip:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Open a terminal and navigate to the repository directory.

2. Start an updater loop (choose Apple Music or Spotify):

    ```shell
    # Apple Music
    ./start-apple-music-updater.sh

    # Spotify
    ./start-spotify-updater.sh
    ```

    Each starter runs the unified updater every 5 seconds. You can also run the unified updater directly and choose a source by arg or env:

    ```shell
    # one-shot, Apple
    ./update.sh applemusic

    # one-shot, Spotify
    ./update.sh spotify

    # or via env var (arg takes precedence over env)
    NOW_PLAYING_SOURCE=applemusic ./update.sh
    NOW_PLAYING_SOURCE=spotify ./update.sh
    ```

    Output files (namespaced by source) use this 4-line format (newlines between fields):

    ```
    "<song name>"
    <artist name>
    <album name>
    <year (if available)>
    ```

    Notes:
    - For Spotify, the 4th line (year) is intentionally blank.
    - Apple output file: `_data/apple_current_song.txt`
    - Spotify output file: `_data/spotify_current_song.txt`

    Any logging will be written to `_logs/update_<YYYY-MM-DD>.log`.

    You can also directly use the unified Python CLI without the shell script:

    ```shell
    # Print four-line info and update files
    python3 -m now_playing applemusic --info
    python3 -m now_playing spotify --info

    # Get first artwork path
    python3 -m now_playing spotify --image

    # Update OBS image source
    python3 -m now_playing applemusic --update-obs
    ```

3. Point your display program to the appropriate file:

    - Apple Music: `_data/apple_current_song.txt`
    - Spotify: `_data/spotify_current_song.txt`

4. To stop an updater running in the background:

    ```shell
    # Apple Music
    ./stop-apple-music-updater.sh

    # Spotify
    ./stop-spotify-updater.sh
    ```

    These send a termination signal to the updater process using the PID stored in their respective PID files.

## Artwork files

- Apple Music artworks list: `_data/apple_now_playing_artworks.txt`
- Spotify artworks list: `_data/spotify_now_playing_artworks.txt`

Each file contains one or more absolute file paths (one per line) pointing to cached cover images under `~/.now-playing/artwork-cache/`. When no artwork is available, an empty file is created.

## OBS integration

- Image sources are updated via obs-websocket:
  - Apple Music image source name: `NPImageApple`
  - Spotify image source name: `NPImageSpotify`
- Create corresponding Text (GDI+/Freetype2) sources that read from the namespaced song files above if you want on-screen text.
- The Python client connects to `localhost:4455` (OBS 28+ default) with the configured password inside the scripts.

## Permissions

macOS will prompt to allow these scripts to control Apple Music and Spotify. Approve the prompts or enable in System Settings → Privacy & Security → Automation.

## Structure of track and music player classes (Apple Music)

### Music App
```python
{
    AirPlayEnabled = 0;
    EQEnabled = 0;
    converting = 0;
    currentAirPlayDevices =     (
        "<SBObject @0x600003b7a2e0: <class 'cAPD'> id 33 of application \"Music\" (2126)>"
    );
    fixedIndexing = 0;
    frontmost = 0;
    fullScreen = 0;
    mute = 0;
    name = Music;
    objectClass = "<NSAppleEventDescriptor: 'capp'>";
    playerPosition = "47.0359992980957";
    playerState = "<NSAppleEventDescriptor: 'kPSP'>";
    shuffleEnabled = 0;
    shuffleMode = "<NSAppleEventDescriptor: 'kShS'>";
    songRepeat = "<NSAppleEventDescriptor: 'kAll'>";
    soundVolume = 100;
    version = "1.4.5";
    visualsEnabled = 0;
}
```

To determine if the the Music app is playing a track, we check against
the `playerState` key. If the integer value is `1800426320`, then the
Music app is playing a track.  I don't know why it is this value.

### Track
```python
{
    EQ = "";
    album = Floodland;
    albumArtist = "The Sisters of Mercy";
    albumDisliked = 0;
    albumFavorited = 0;
    artist = "The Sisters of Mercy";
    bitRate = 177;
    bookmark = 0;
    bookmarkable = 0;
    bpm = 120;
    category = "";
    cloudStatus = "<NSAppleEventDescriptor: 'kMat'>";
    comment = " 00000601 0000070C 000017A8 0000198F 00034F59 00015D0C 00005664 00005F53 00048AE8 00048AFF";
    compilation = 0;
    composer = "Andrew Eldritch";
    databaseID = 40964;
    dateAdded = "2022-05-10 12:58:00 +0000";
    discCount = 1;
    discNumber = 1;
    disliked = 0;
    duration = "421.0409851074219";
    enabled = 1;
    episodeNumber = 0;
    favorited = 0;
    finish = "421.0409851074219";
    genre = "Goth rock";
    grouping = "";
    id = 144915;
    index = 44;
    kind = "MPEG audio file";
    location = "file:///Users/coj/Dropbox/Music/Artists/The%20Sisters%20of%20Mercy/Floodland/The%20Sisters%20of%20Mercy%20-%20Floodland%20-%2001%20-%20Dominion%20_%20Mother%20Russia.mp3";
    lyrics = "";
    mediaKind = "<NSAppleEventDescriptor: 'kMdS'>";
    modificationDate = "2020-06-16 03:08:27 +0000";
    movement = "";
    movementCount = 0;
    movementNumber = 0;
    name = "Dominion / Mother Russia";
    objectClass = "<NSAppleEventDescriptor: 'cFlT'>";
    objectDescription = "";
    persistentID = F62D93D366BC9681;
    playedCount = 3;
    playedDate = "2024-05-23 23:53:49 +0000";
    rating = 0;
    sampleRate = 44100;
    shufflable = 1;
    size = 9811667;
    skippedCount = 0;
    sortAlbum = "";
    sortAlbumArtist = "Sisters of Mercy, The";
    sortArtist = "Sisters of Mercy, The";
    sortComposer = "Eldritch, Andrew";
    sortName = "";
    start = 0;
    time = "7:01";
    trackCount = 10;
    trackNumber = 1;
    unplayed = 0;
    volumeAdjustment = 0;
    work = "";
    year = 1987;
}
```




## Notes

- The `updater.pid` file is used to store the PID of the updater process. Do not delete or modify this file while the updater is running.

- If you want to change the interval at which the `update.sh` script is executed, you can modify the `sleep` duration in the `start-updater.sh` function.
