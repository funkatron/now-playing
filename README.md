# Dead Agent "Now Playing" Scripts

This repository contains scripts to retrieve and display the currently playing song from various music players on MacOS.

Right now only Apple Music is supported, but I plan to add support for audio sources in the future.

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

1. Open a terminal and navigate to the directory where the `start-updater.sh` script is located.

2. Run the script using the following command:

    ```shell
    ./start-updater.sh
    ```

    The updater will start running in the background and will execute the `update.sh` script every 5 seconds.

    When the `update.sh` script is executed, it will retrieve the currently playing song from Apple Music and write it to the ` `. The text is formatted as follows, with `\n` used for newlines:

    ```
    "<song name>"
    <artist name>
    <album name>
    <year (if available)>
    ```

    Any logging will be written to the `_logs/update_<YYYY-MM-DD>.log` file.

3. Point the program you want to *display* the currently playing song to the `_data/current_song.txt` file. The information in this file will be updated every time the `update.sh` script is executed.

4. To stop the updater, you can use the following command:

    ```shell
    ./stop-updater.sh
    ```

    This will send a termination signal to the updater process using the PID stored in the `updater.pid` file.

## Structure of track and music player classes

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
