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

    When the `update.sh` script is executed, it will retrieve the currently playing song from Apple Music and write it to the `_data/current_song.txt`. The text is formatted as follows, with `\n` used for newlines:

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

## Note

- The `updater.pid` file is used to store the PID of the updater process. Do not delete or modify this file while the updater is running.

- If you want to change the interval at which the `update.sh` script is executed, you can modify the `sleep` duration in the `start-updater.sh` function.
