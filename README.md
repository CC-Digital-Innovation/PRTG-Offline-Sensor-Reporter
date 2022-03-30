# PRTG-Duplicate-Device-Finder

## Summary
This script will make an Opsgenie alert that reports any unknown, down, down
(acknowledged), or down (partial) sensors in a given instance of PRTG.

_Note: If you have any questions or comments you can always use GitHub
discussions, or email me at farinaanthony96@gmail.com._

#### Why
Provides insight for the current offline sensors in PRTG in order for those
sensors to be corrected. This helps ensure that the devices being monitored in 
PRTG are online and fully operational.

## Requirements
- Python >= 3.10.2
- configparser >= 5.2.0
- requests >= 2.27.1

## Usage
- Edit the config file with relevant PRTG / Opsgenie access information.

- Add custom substrings to filter through PRTG probes, groups, devices, and 
  sensors to report on only relevant sensors.

- Add Opsgenie alert information to customize the alert message and responders 
  of the alert.

- Simply run the script using Python:
  `python PRTG-Offline-Sensor-Reporter.py`

## Compatibility
Should be able to run on any machine with a Python interpreter. This script
was only tested on a Windows machine running Python 3.10.2.

## Disclaimer
The code provided in this project is an open source example and should not
be treated as an officially supported product. Use at your own risk. If you
encounter any problems, please log an
[issue](https://github.com/CC-Digital-Innovation/PRTG-Offline-Sensor-Reporter/issues).

## Contributing
1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request ツ

## History
- version 2.0.0 - 2022/03/30
    - Added custom PRTG filtering system
    - Added customization options for the Opsgenie alert.
    - Updated README
    - Updated packages / Python version
  

- version 1.0.0 - 2021/11/30
    - (initial release)

## Credits
Anthony Farina <<farinaanthony96@gmail.com>>
