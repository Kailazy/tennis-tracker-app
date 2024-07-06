# tracker

## SETUP

To setup this app on the RaspberryPI you need to install a few packages:
	
	$ sudo apt-get update
	$ sudo apt-get install git python3 python3-pip python3-numpy python3-opencv

and the following python libraries:

	$ sudo pip3 install imutils flask importlib argparse datetime json2 getkey minimalmodbus wave pyaudio deepdiff

To be able to automatically load from GitHub on start you need to follow the instructions compiled from these articles (specific instructions below):
* https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent
* https://stackoverflow.com/questions/3466626/how-to-permanently-add-a-private-key-with-ssh-add-on-ubuntu

Or specifically:
1. login to your RaspberryPI and run the following commands:
```
$ ssh-keygen -t ed25519 -C "your_git_username_or_email" -f ~/.ssh/git-key   # generate a private/public key pair
$ eval `ssh-agent -s`                                                         # point the local session to the ssh agent
$ ssh-add ~/.ssh/git-key                                                      # adds the private ssh key to session (only for the current session / first clone)
$ more ~/.ssh/git-key.pub                                                     # displays the generated public key
```

2. Now edit your SSH config file to add the SSH key if you want to permanently make it available on reboot (create the file if it doesn't exist)
```
$ pico ~/.ssh/config
```
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;and create or update the following section:
```
Host github.com
	User git
	IdentityFile ~/.ssh/git-key
```

3. Now register the public key in GitHub by:
	* loging into your github.com account;
	* click on your profile icon at the very top right and select Settings
	* click on the ```SSH and GPG keys``` menu from the left nave
	* click to add ```New SSH key``` and type ```git-key``` in the title field; then copy the above line from step 1 starting with ```ssh-ed25519``` into the key field
	* type your password to confirm adding the SSH key; you should now see the added SSH key in your GitHub account

4. The very first time you need to clone the repo and optionally change to the branch you want to work with
```
$ git clone git@github.com:ivolazy/tracker-app.git        # clones the repo the very first time (if SSH key works you should not see user/pass)
$ cd tracker-app                                          # cd into the directory
$ git checkout development                                # OPTIONAL: change to the development branch
$ git pull                                                # this is redundant, but shows if ssh agent works without asking you for user/pass
```

## RUN
To run the app, login to your RaspberryPI and run the following command:
```$ cd tracker-app
$ ./start
```
This command will automatically run `git pull` every time it runs to make sure the latest files are updated in the RaspberryPI. This command is also automatically restarted when you click on the `Restart` button in the Web UI.

The result of the above command will look something like this:

```
Already up to date.
Reset complete
Running
Detection Started
 * Serving Flask app "tracker" (lazy loading)
 * Environment: production
   WARNING: Do not use the development server in a production environment.
   Use a production WSGI server instead.
 * Debug mode: on
 * Running on http://10.25.0.129:5000/ (Press CTRL+C to quit)
```

Copy the `Running on` http address from the output and paste it in a browser window to see the Web UI.

## BUGS
* current session charts' dropdowns don't get updated from the incoming new events in real time
* brush from the context doesn't propagate to all
* zoom after brush-left/right starts from previous position
* all charts should be on the same X scale
* charts don't show the gray back-line
* comparing motion_stats to voltage_stats may not yield exactly the same x for the hovers - use the timestamps as a comparator
* pyaudio doesn't work
* under certain conditions the RPI freezes
* RESTART doesn't work
* Video showing black on MacOS
* Video showing error on RPI
* Not enough power to move over obstacles
* Text on screen should be done by the browser (not by video streamer - takes too much computation)
* Joystick drag doesn't work

## TODO
* move chart.js in a separate file
* Add version to DB, schemas, and test for them in the code
* move the threading of detection into the detection class (just like Sound)
* add detection events to the event log
* connect via Bluetooth
* remove evals (not secure)
* add dimmed spinner and counter down when restarting
* add password to DB and images
* capture images in the event log/storage folder
* position regulation to compensate loss of power with reduction of angle to avoid jittery rush
* Debug Flask in MacOS
* Change event format to be time, type, details (dict not list) and flip all the events in the DB

## HARDWARE
* Print new 15T5 gears
* Add on/off switch
* Install new powertrain with 17T5 and 51T5 gears