# OctoPrint-picoLCD-Progress

This fork of OctoPrint-DetailedProgress writes the progress to a picoLCD device that is running on the server, as long as pypicolcd is installed.

M117 is no longer used. Search for M117 (which still appears in comments) to see what has changed.

## Setup
You must have a picoLCD device. Only the picoLCD 256x64 Sideshow is tested.

1. Install pypicolcd from https://github.com/poikilos/pypicolcd in the same virtualenv as your OctoPrint installation, such as:
```
source ~/OctoPrint/venv/bin/activate  # change to match your virtualenv (only necessary if you installed OctoPrint using virtualenv).
pip install https://github.com/poikilos/pypicolcd/archive/master.zip
```

2.  Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually in the same virtualenv as OctoPrint, such as:

```
source ~/OctoPrint/venv/bin/activate  # change to match your virtualenv (only necessary if you installed OctoPrint using virtualenv).
pip install https://github.com/poikilos/OctoPrint-picoLCD-Progress/archive/master.zip
```


## Configuration

``` yaml
plugins:
  picolcdprogress:
    # Number of seconds (minimum) to rotate the messages
    time_to_change: 10
    eta_strftime: "%H:%M:%S Day %d"
    etl_format: "{hours:02d}:{minutes:02d}:{seconds:02d}"
    # LCD server (blank for localhost; If the pypicolcd server is
    # configured for remote access, you must set host to your LAN IP or
    # hostname, even if it is your own LAN IP or hostname, since in that
    # case the service would not be bound to 127.0.0.1 but rather the
    # LAN IP).
    lcd_server: ""
    # Messages to display. Placeholders:
    # - completion : The % completed
    # - printTimeLeft : A string in the format "HH:MM:SS" with how long the print still has left
    # - ETA : The date and time formatted in "%H:%M:%S Day %d" that the print is estimated to be completed
    # - filepos: The current position in the file currently being printed
    messages:
      - "{completion:.2f}% complete"
      - "ETL: {printTimeLeft}"
      - "ETA: {ETA}"
```

## Developer Notes
### Job data

```Python
currentData = self._printer.get_current_data()
currentData = self._sanitize_current_data(currentData)
currentData.get("job")
```

```json
{
  "averagePrintTime": null,
  "estimatedPrintTime": 2828.025893510537,
  "filament": {
    "tool0": {
      "length": 813.9770699999954,
      "volume": 0.0
    }
  },
  "file": {
    "date": 1579921462,
    "display": "harbor_top_-_brick (3DPP JA3S).gcode",
    "name": "harbor_top_-_brick_(3DPP_JA3S).gcode",
    "origin": "local",
    "path": "tabletop/catan-style-boardgame/harbor_top_-_brick_(3DPP_JA3S).gcode",
    "size": 1593876
  },
  "lastPrintTime": null,
  "user": "pi"
}
```
