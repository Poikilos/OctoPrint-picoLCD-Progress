# coding=utf-8
from __future__ import absolute_import
import time
import socket

import octoprint.plugin
import octoprint.util
import traceback
from octoprint.events import Events
import copy
from datetime import datetime

from pypicolcd import lcdclient

class PicoLCDProgressPlugin(octoprint.plugin.EventHandlerPlugin,
                            octoprint.plugin.TemplatePlugin,
                            octoprint.plugin.SettingsPlugin,
                            octoprint.plugin.StartupPlugin):
    _last_updated = 0.0
    _last_message = 0
    _repeat_timer = None
    _etl_format = ""
    _eta_strftime = ""
    _messages = []
    _picolcd_params = {"x": 0, "y": 0}
    _lcd_server = ""
    _prev_msg = None
    lcd_center = 128
    lcd_my_line_count = 3
    first = True

    def on_after_startup(self):
        # self._logger.info(" (lcd_server: {})".format(
        #     self._settings.get(["lcd_server"])
        # ))
        pass

    def is_blank(self, s):
        """Check if the string is None, empty, or whitespace-only."""
        return (s is None) or (len(s.strip()) == 0)

    def _update_picolcd_params(self):
        """Prepare to transfer applicable settings to lcdclient"""
        if not self.is_blank(self._lcd_server):
            self._picolcd_params["host"] = self._lcd_server
        else:
            if "host" in self._picolcd_params:
                del self._picolcd_params["host"]

    def show_picolcd_msg(self, msg, flash=False, clear=False, x=0, y=0,
                         refresh=True):
        """Send a message to the pypicolcd framebuffer."""
        self._update_picolcd_params()
        if msg != self._prev_msg:
            self._prev_msg = msg
            action = copy.deepcopy(self._picolcd_params)
            action["lines"] = [msg]
            if flash:
                action["flash"] = True
            if clear:
                action["clear"] = True
            if x is not None:
                action["x"] = x
            if y is not None:
                action["y"] = y
            if refresh:
                action["refresh"] = True
            # self._logger.info("Sending {}...".format(action))
            results = lcdclient.send_action(action)
            # TODO: do something with results
            # if not results["status"] == "OK":

    def show_start_stop_msg(self, msg, clear=False, flash=True):
        self.show_picolcd_msg(msg, flash=flash, clear=clear,
                              x=self.lcd_center,
                              y=8*(self.lcd_my_line_count-1))

    def on_event(self, event, payload):
        now = datetime.now()
        # See
        # <https://docs.python.org/2/library/datetime.html#strftime-and-
        # strptime-behavior>
        # %m zero-padded month
        # formerly %M:%S %b %d
        # %b (locale's abbreviated month name)
        ts = now.strftime("%H%M %b%d")  # There isn't anymore space@128
        if event == Events.PRINT_STARTED:
            self._logger.info("Printing started. PicoLCD progress started.")
            self._etl_format = self._settings.get(["etl_format"])
            self._eta_strftime = self._settings.get(["eta_strftime"])
            self._messages = self._settings.get(["messages"])
            self._lcd_server = self._settings.get(["lcd_server"])
            self._repeat_timer = octoprint.util.RepeatedTimer(
                self._settings.get_int(["time_to_change"]),
                self.do_work
            )
            self._repeat_timer.start()
            self.first = True
            self.show_start_stop_msg("starting from: {}".format(ts),
                                     flash=True, clear=True)
            self.first = True

        elif event in (Events.PRINT_DONE, Events.PRINT_FAILED,
                       Events.PRINT_CANCELLED):
            if self._repeat_timer != None:
                self._repeat_timer.cancel()
                self._repeat_timer = None
            # self._printer.commands("M117 Print Done")
            msg = "done job"
            min_len = 8
            percent_msg = "stopped"
            if event == Events.PRINT_CANCELLED:
                msg = "canceled"
            elif event == Events.PRINT_FAILED:
                msg = "failed"
            else:
                percent_msg = "*100%*"
            self._logger.info("The print stopped: {}.".format(msg))
            msg = msg.ljust(min_len, "-")  # ljust pads on right
            # See <https://stackoverflow.com/a/5676673>
            # Or: msg = "{:-<8}".format(msg)
            # but '%' is more Python 2 friendly: "%-8s" % msg
            # - but only does spaces (`-` makes it left justified)
            # - and ljust works with Python 2.
            # - then there's `('hi' + '-'*min_len)[:min_len]` lol
            self.show_picolcd_msg(percent_msg, x=0, y=8, clear=False,
                                  refresh=False)
            self.show_start_stop_msg(msg, flash=True,
                                     clear=False)
            # The message above is designed to overwrite the word
            # "starting" in "starting from:" written in the previous
            # call to show_start_stop_msg.
            self.first = True
        elif event == Events.CONNECTED:
            ip = self._get_host_ip()
            if not ip:
                ip = "?"
            # self._printer.commands("M117 IP {}".format(ip))
            self.show_start_stop_msg("connected {} {}".format(ip, ts),
                                     flash=True, clear=True)
            self.first = True

    def do_work(self):
        if not self._printer.is_printing():
            # we have nothing to do here
            self.first = True
            return
        try:
            currentData = self._printer.get_current_data()
            currentData = self._sanitize_current_data(currentData)
            # message = self._get_next_message(currentData)
            # self._printer.commands("M117 {}".format(message))
            # self.show_picolcd_msg("{}".format(message), flash=False,
            #                       clear=True)
            messages = self._get_all_messages(currentData)
            x = 0
            y = 0
            refresh = False
            for i in range(len(messages)):
                if i == (len(messages) - 1):
                    refresh = True
                if i == self.lcd_my_line_count:
                    y = 8  # don't overwrite right side of job name
                    x = self.lcd_center
                # clear = self.first
                clear = False  # don't overwrite the start time.
                self.show_picolcd_msg(messages[i], clear=clear, x=x,
                                      y=y, refresh=refresh)
                self.first = False
                y += 8

        except Exception as e:
            self._logger.info(
                "Caught an exception {0}\nTraceback:{1}".format(
                              e,
                              traceback.format_exc()
                )
            )

    def _sanitize_current_data(self, currentData):
        if (currentData["progress"]["printTimeLeft"] == None):
            currentData["progress"]["printTimeLeft"] = currentData["job"]["estimatedPrintTime"]
        if (currentData["progress"]["filepos"] == None):
            currentData["progress"]["filepos"] = 0
        if (currentData["progress"]["printTime"] == None):
            currentData["progress"]["printTime"] = currentData["job"]["estimatedPrintTime"]

        currentData["progress"]["printTimeLeftString"] = "No ETL yet"
        currentData["progress"]["ETA"] = "No ETA yet"
        accuracy = currentData["progress"]["printTimeLeftOrigin"]
        if accuracy:
            if accuracy == "estimate":
                accuracy = "Best"
            elif accuracy == "average" or accuracy == "genius":
                accuracy = "Good"
            elif accuracy == "analysis" or accuracy.startswith("mixed"):
                accuracy = "Medium"
            elif accuracy == "linear":
                accuracy = "Bad"
            else:
                accuracy = "ERR"
                self._logger.debug("Caught unmapped accuracy value: {0}".format(accuracy))
        else:
            accuracy = "N/A"
        currentData["progress"]["accuracy"] = accuracy

        #Add additional data
        try:
            currentData["progress"]["printTimeLeftString"] = self._get_time_from_seconds(currentData["progress"]["printTimeLeft"])
            currentData["progress"]["ETA"] = time.strftime(self._eta_strftime, time.localtime(time.time() + currentData["progress"]["printTimeLeft"]))
        except Exception as e:
            self._logger.debug("Caught an exception trying to parse data: {0}\n Error is: {1}\nTraceback:{2}".format(currentData,e,traceback.format_exc()))

        return currentData


    def _get_all_messages(self, currentData):
        results = []
        job_name = None
        job = currentData.get("job")
        f = None
        if job is not None:
            f = job.get("file")
        else:
            self._logger.info("job is None.")
        if f is not None:
            job_name = f.get("display")  # friendly name or filename
            if job_name is None:
                self._logger.info("job['file']['display'] is None.")
                job_name = f.get("name")  # filename
                if job_name is not None:
                    job_name = "'{}'".format(job_name)
                else:
                    self._logger.info("job['file']['name'] is None.")
        else:
            self._logger.info("job['file'] is None.")
        if job_name is None:
            self._logger.info("job_name is unknown.")
            job_name = "?"
        else:
            # There is a possibility that 'display' could be anything,
            # so don't truncate filenames if they contain a '.' but not
            # an extension. Instead, only remove known extensions.
            known_exts = [".gcode", ".g", ".x3d"]
            for ext in known_exts:
                if job_name.lower().endswith(ext):
                    job_name = job_name[:len(job_name)-len(ext)]
        results.append(str(job_name))
        for i in range(len(self._messages)):
            message = self._messages[i]
            this_msg = message.format(
                completion = currentData["progress"]["completion"],
                printTimeLeft = currentData["progress"]["printTimeLeftString"],
                ETA = currentData["progress"]["ETA"],
                filepos = currentData["progress"]["filepos"],
                accuracy = currentData["progress"]["accuracy"],
            )
            results.append(this_msg)
        return results

    def _get_next_message(self, currentData):
        message = self._messages[self._last_message]
        self._last_message += 1
        if (self._last_message >= len(self._messages)):
            self._last_message = 0
        return message.format(
            completion = currentData["progress"]["completion"],
            printTimeLeft = currentData["progress"]["printTimeLeftString"],
            ETA = currentData["progress"]["ETA"],
            filepos = currentData["progress"]["filepos"],
            accuracy = currentData["progress"]["accuracy"],
        )

    def _get_time_from_seconds(self, seconds):
        hours = 0
        minutes = 0
        if seconds >= 3600:
            hours = int(seconds / 3600)
            seconds = seconds % 3600
        if seconds >= 60:
            minutes = int(seconds / 60)
            seconds = seconds % 60
        return self._etl_format.format(**locals())

    def _get_host_ip(self):
        return [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]

    ##~~ Settings

    def get_template_configs(self):
        """
        Tell OctoPrint not to use custom bindings. See
        <https://docs.octoprint.org/en/master/plugins/
        gettingstarted.html#frontend-fun-how-to-add-functionality-to-
        octoprint-s-web-interface>. If you do it this way, you do not
        need to override get_template_vars.
        """
        return [
            dict(type="settings", custom_bindings=False)
        ]


    def get_settings_defaults(self):
        return dict(
            messages = [
                "{completion:.2f}%",
                "ETL {printTimeLeft}",
                "ETA {ETA}"  #,
                # "{accuracy} accuracy"
            ],
            eta_strftime = "%H:%M:%S %b %d",
            etl_format = "{hours:02d}h{minutes:02d}m{seconds:02d}s",
            time_to_change = 10,
            lcd_server = None
        )

    ##~~ Softwareupdate hook

    def get_update_information(self):
        return dict(
            picolcdprogress=dict(
                displayName="picoLCD Progress Plugin",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="poikilos",
                repo="OctoPrint-picoLCD-Progress",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/poikilos/OctoPrint-picoLCD-Progress/archive/{target_version}.zip"
            )
        )

# The __plugin_name__ here can differ from setup.py for using spaces.
__plugin_name__ = "picoLCD Progress Plugin"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PicoLCDProgressPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    }

