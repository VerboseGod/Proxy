import asyncio
import logging
import os
import threading
import tkinter
from tkinter import scrolledtext

import proxy


class ProxyThread(threading.Thread):
    def __init__(self, loop, verbose, port, ip, banned_port, special=None):
        super().__init__()
        self.setName("proxy_thread")
        self.setDaemon(True)
        self.loop = loop  # Loop to call
        self.verbose = verbose
        self.port = port
        self.ip = ip
        self.special = special
        self.banned_port = banned_port if banned_port != 'None' else None

    def run(self):
        proxy.main(loop=self.loop, verbose_level=self.verbose, ip=self.ip, port=self.port, bport=self.banned_port,
                   special=self.special)


class ProxyApplication(tkinter.Tk):  # Main application window
    def __init__(self, *args, **kwargs):
        tkinter.Tk.__init__(self, *args, **kwargs)
        self.title("Proxy")
        self.resizable(False, False)  # Making the windows not resizable on the x and y directions
        self.frames = dict()  # Frames dictionary
        container = tkinter.Frame(self)

        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        for F in (MainWin, ConfigurationWin, SiteConfigurationWin, DetailsWin):
            frame = F(container, self)
            self.frames[F] = frame

            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(MainWin)

    def show_frame(self, cont):  # Cont = Container
        frame = self.frames[cont]
        frame.tkraise()


class MainWin(tkinter.Frame):  # Main Window
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.columnconfigure(0, weight=0)
        self.rowconfigure(0, weight=0)

        self.controller = controller
        self.btn_start = None
        self.img_start = None
        self.img_settings = None
        self.img_bg = None
        self.lbl_bg = None
        self.btn_settings = None
        self.proxy_thread = None  # The main thread

        self.img_bg = tkinter.PhotoImage(file=os.path.join(os.getcwd(), "background_image.gif"))
        self.lbl_bg = tkinter.Label(self, image=self.img_bg)
        self.lbl_bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.btn_start = tkinter.Button(self,
                                        state=tkinter.NORMAL,
                                        command=self.start_proxy)
        self.img_start = tkinter.PhotoImage(file=os.path.join(os.getcwd(), "start_button.gif"), width=200, height=200)
        self.btn_start.config(image=self.img_start)
        self.btn_start.place(relx=0.25, rely=0.5, anchor=tkinter.CENTER)

        self.btn_settings = tkinter.Button(self, text="Settings",
                                           state=tkinter.NORMAL,
                                           command=lambda: self.controller.show_frame(ConfigurationWin))
        self.img_settings = tkinter.PhotoImage(file=os.path.join(os.getcwd(), "settings_button.gif"))
        self.btn_settings.config(image=self.img_settings)
        self.btn_settings.place(relx=0.75, rely=0.5, anchor=tkinter.CENTER)

        if not os.path.exists(os.path.exists(os.path.join(os.getcwd(), "options.csv"))):
            self.btn_start.config(state=tkinter.DISABLED)

    def start_proxy(self):
        if os.path.exists(os.path.join(os.getcwd(), "options.csv")):
            self.controller.frames[ConfigurationWin].ent_ip.config(state=tkinter.DISABLED)
            self.controller.frames[ConfigurationWin].ent_port.config(state=tkinter.DISABLED)
            pre_filled_dict = dict()
            sites = dict()
            from csv import DictReader
            with open(os.path.join(os.getcwd(), "options.csv"), newline='') as csvfile:
                opt_reader = DictReader(csvfile)
                for row in opt_reader:
                    pre_filled_dict['verbose'] = row['verbose']
                    pre_filled_dict['ip'] = row['ip']
                    pre_filled_dict['port'] = row['port']
                    pre_filled_dict['banned_protocol'] = row['banned_protocol']

            if os.path.exists(os.path.join(os.getcwd(), "sites.csv")):
                with open(os.path.join(os.getcwd(), "sites.csv"), newline='') as csvfile:
                    site_reader = DictReader(csvfile)
                    for row in site_reader:
                        sites[row['host']] = dict()
                        sites[row['host']]['host'] = row['host']
                        sites[row['host']]['blacklist'] = row['blacklist']
                        sites[row['host']]['alert_bool'] = row['alert_bool']
                        sites[row['host']]['words_to_remove'] = row['words_to_remove']
                        sites[row['host']]['words_to_replace'] = row['words_to_replace']
            else:
                sites = None

            self.proxy_thread = ProxyThread(loop=asyncio.new_event_loop(),
                                            verbose=pre_filled_dict['verbose'],
                                            port=pre_filled_dict['port'],
                                            ip=pre_filled_dict['ip'], special=sites,
                                            banned_port=pre_filled_dict['banned_protocol'])
            self.proxy_thread.start()
            self.btn_start.config(state=tkinter.DISABLED, text="Proxy Is Running")
            self.btn_settings.config(state=tkinter.NORMAL)

            self.controller.show_frame(DetailsWin)
        else:
            from tkinter import messagebox
            tkinter.messagebox.showinfo("Error", "Configure settings first")


class DetailsWin(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.srt_logging_window = None
        self.btn_settings = None
        self.logger = None  # Text logger for the auto-scrolling widget

        self.btn_settings = tkinter.Button(self, text="Settings", state=tkinter.NORMAL,
                                           command=lambda: controller.show_frame(ConfigurationWin))
        self.btn_settings.grid(row=1, column=0, sticky="NSEW")

        self.srt_logging_window = scrolledtext.ScrolledText(self,
                                                            wrap='word',
                                                            bg='beige',
                                                            state=tkinter.DISABLED)
        self.srt_logging_window.grid(row=0, column=0)

        text_handler = LoggingHandler(self.srt_logging_window)
        text_handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))
        self.logger = logging.getLogger()
        self.logger.addHandler(text_handler)


class ConfigurationWin(tkinter.Frame):  # Configuration Window
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)

        self.controller = controller
        self.ent_ip = None
        self.ent_port = None
        self.ent_site_host = None
        self.btn_add = None
        self.btn_advanced = None
        self.btn_remove = None
        self.btn_apply = None
        self.btn_close = None
        self.btn_edit = None
        self.verbose_option = None
        self.verbose_option_menu = None
        self.banned_protocol_option = None
        self.banned_protocol_option_menu = None
        self.lb_sites = None
        self.changes = dict()  # The changes dictionary, with each key is a different value
        self.saved_sites = dict()
        pre_filled_dict = dict()  # Pre-filled dict

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # See if there are saved options
        from csv import DictReader
        try:
            with open(os.path.join(os.getcwd(), "options.csv"), newline='') as csvfile:
                opt_reader = DictReader(csvfile)
                for row in opt_reader:
                    pre_filled_dict['verbose'] = str(row['verbose'])
                    pre_filled_dict['ip'] = str(row['ip'])
                    pre_filled_dict['port'] = str(row['port'])
                    pre_filled_dict['banned_protocol'] = str(row['banned_protocol'])
        except (FileNotFoundError, KeyError):
            pre_filled_dict = None

        label = tkinter.Label(self, text="Configuration Window", font=("Verdana", 15))
        label.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

        labels_text = ("Verbose level:", "IP:", "Port:", "Host to ban", "Protocol to ban:")

        for i in range(len(labels_text)):
            label = tkinter.Label(self, text=labels_text[i], font=("New Roman", 10))
            label.grid(row=i + 1, column=0, padx=5, pady=5, sticky="nsw")

        self.verbose_option = tkinter.StringVar(self)
        self.verbose_option.set(pre_filled_dict['verbose']) if pre_filled_dict else self.verbose_option.set("select")
        self.verbose_option_menu = tkinter.OptionMenu(self, self.verbose_option, "debug", "info", "error")
        self.verbose_option_menu.grid(row=1, column=1, pady=5, sticky="nsew")
        self.ent_ip = tkinter.Entry(self)
        self.ent_ip.grid(row=2, column=1, pady=5, sticky="nsew")
        self.ent_ip.insert(0, pre_filled_dict['ip']) if pre_filled_dict else None
        self.ent_port = tkinter.Entry(self)
        self.ent_port.grid(row=3, column=1, pady=5, sticky="nsew")
        self.ent_port.insert(0, pre_filled_dict['port']) if pre_filled_dict else None
        self.ent_site_host = tkinter.Entry(self)
        self.ent_site_host.grid(row=4, column=1, pady=5, sticky="nsew")
        self.banned_protocol_option = tkinter.StringVar(self)
        self.banned_protocol_option.set(pre_filled_dict['banned_protocol']) if pre_filled_dict else \
            self.banned_protocol_option.set("None")
        self.banned_protocol_option_menu = tkinter.OptionMenu(self, self.banned_protocol_option,
                                                              "HTTP (80)", "HTTPS (443)", "None")
        self.banned_protocol_option_menu.grid(row=5, column=1, pady=5, sticky="nsew")

        self.btn_add = tkinter.Button(self, text="Add",
                                      state=tkinter.NORMAL, command=self.add_command)
        self.btn_add.grid(row=4, column=2, pady=5, padx=5, sticky="nsew")
        self.btn_advanced = tkinter.Button(self, text="Advanced",
                                           state=tkinter.NORMAL,
                                           command=lambda: self.controller.show_frame(SiteConfigurationWin))
        self.btn_advanced.grid(row=5, column=2, pady=5, padx=5, sticky="nsew")
        self.btn_remove = tkinter.Button(self, text="Remove",
                                         state=tkinter.NORMAL,
                                         command=self.remove_command)
        self.btn_remove.grid(row=6, column=2, pady=5, padx=5, sticky="nsew")
        self.btn_apply = tkinter.Button(self, text="Apply", state=tkinter.NORMAL,
                                        command=self.apply)
        self.btn_apply.grid(row=7, column=3, padx=5, pady=5, sticky="nsew")
        self.btn_close = tkinter.Button(self, text="Close", state=tkinter.NORMAL,
                                        command=lambda: self.controller.show_frame(DetailsWin) if
                                        self.controller.frames[MainWin].proxy_thread else
                                        self.controller.show_frame(MainWin))
        self.btn_close.grid(row=7, column=4, padx=5, pady=5, sticky="nsew")

        self.lb_sites = tkinter.Listbox(self)
        self.lb_sites.grid(row=0, column=3, rowspan=7, columnspan=2, padx=5, pady=5, sticky="nsew")

        # See if there are saved sites
        from csv import DictReader
        try:
            with open(os.path.join(os.getcwd(), "sites.csv"), newline='') as csvfile:
                site_reader = DictReader(csvfile)
                for row in site_reader:
                    self.saved_sites[row['host']] = dict()
                    self.saved_sites[row['host']]['host'] = row['host']
                    self.saved_sites[row['host']]['blacklist'] = row['blacklist']
                    self.saved_sites[row['host']]['alert_bool'] = row['alert_bool']
                    self.saved_sites[row['host']]['words_to_remove'] = row['words_to_remove']
                    self.saved_sites[row['host']]['words_to_replace'] = row['words_to_replace']

                    self.lb_sites.insert(tkinter.END, row['host'])
        except (FileNotFoundError, KeyError):
            self.lb_sites.delete(0, tkinter.END)

    def remove_command(self):
        self.saved_sites.pop(self.lb_sites.get(tkinter.ANCHOR), None)
        self.lb_sites.delete(tkinter.ANCHOR)

    def add_command(self):
        self.ent_site_host.config(state=tkinter.DISABLED)
        host = self.ent_site_host.get()  # Get the host from the entry
        self.ent_site_host.config(state=tkinter.NORMAL)  # Release it
        self.ent_site_host.delete(0, tkinter.END)  # Reset field in entry
        temp_sites = []

        for site in self.lb_sites.get(0, tkinter.END):
            temp_sites.append(site)
        if host not in temp_sites and host is not '':
            self.saved_sites[host] = dict()
            self.saved_sites[host]['host'] = host
            self.saved_sites[host]['blacklist'] = True
            self.saved_sites[host]['alert_bool'] = False,
            self.saved_sites[host]['words_to_remove'] = None
            self.saved_sites[host]['words_to_replace'] = None

            self.lb_sites.insert(tkinter.END, host)
            self.lb_sites.itemconfig(tkinter.END, bg='green')

    def apply(self):
        if self.entries_check():
            self.btn_apply.config(state=tkinter.DISABLED)
            self.btn_add.config(state=tkinter.DISABLED)
            self.btn_remove.config(state=tkinter.DISABLED)
            self.btn_advanced.config(state=tkinter.DISABLED)

            from csv import DictWriter
            with open(os.path.join(os.getcwd(), "options.csv"), 'w', newline='') as csvfile:
                options_names = ['verbose', 'ip', 'port', 'banned_protocol']
                opt_writer = DictWriter(csvfile, fieldnames=options_names)
                opt_writer.writeheader()
                opt_writer.writerow({'verbose': self.verbose_option.get(),
                                     'ip': self.ent_ip.get(),
                                     'port': self.ent_port.get(),
                                     'banned_protocol': self.banned_protocol_option.get()})

            with open(os.path.join(os.getcwd(), "sites.csv"), 'w', newline='') as csvfile:
                options_names = ['host', 'blacklist', 'alert_bool', 'words_to_remove', 'words_to_replace']
                opt_writer = DictWriter(csvfile, fieldnames=options_names)
                opt_writer.writeheader()

                for site in self.saved_sites.keys():
                    opt_writer.writerow({'host': self.saved_sites[site]['host'],
                                         'blacklist': self.saved_sites[site]['blacklist'],
                                         'alert_bool': str(self.saved_sites[site]['alert_bool']),
                                         'words_to_remove': str(self.saved_sites[site]['words_to_remove']),
                                         'words_to_replace': str(self.saved_sites[site]['words_to_replace'])})

            self.btn_apply.config(state=tkinter.NORMAL)
            self.btn_add.config(state=tkinter.NORMAL)
            self.btn_remove.config(state=tkinter.NORMAL)
            self.btn_advanced.config(state=tkinter.NORMAL)

            if self.controller.frames[MainWin].proxy_thread:
                self.controller.show_frame(DetailsWin)
            else:
                self.controller.frames[MainWin].btn_start.config(state=tkinter.NORMAL, text="Start Proxy")
                self.controller.show_frame(MainWin)

    def entries_check(self):
        if self.ent_ip.get() == "":
            self.ent_ip.config(bg="red")
            return False
        elif self.ent_port.get() == "":
            self.ent_port.config(bg="red")
            return False

        self.ent_ip.config(bg="white")
        self.ent_port.config(bg="white")

        return True


class SiteConfigurationWin(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)

        self.controller = controller
        self.btn_save = None
        self.btn_back = None
        self.cb_blacklist = None
        self.cb_popup = None
        self.rb_popup1 = None
        self.rb_popup2 = None
        self.rb_popup3 = None
        self.cb_blacklist_state = None
        self.cb_popup_state = None
        self.rb_popup_state = None
        self.ent_host = None
        self.ent_words_to_remove = None
        self.ent_words_to_replace = None
        self.ent_popup_text = None
        self.ent_popup_special_words = None
        self.ent_popup_special_host_words = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        label = tkinter.Label(self, text="Configure Site", font=("Verdana", 15))
        label.grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")

        label = tkinter.Label(self, text="Host", font=("Verdana", 12))
        label.grid(row=1, column=0, padx=5, pady=5, sticky="nsw")  # Host label

        self.cb_blacklist_state = tkinter.IntVar()
        self.cb_blacklist_state.set(1)
        self.cb_blacklist = tkinter.Checkbutton(self, text="Blacklist this site",
                                                variable=self.cb_blacklist_state,
                                                onvalue=1, offvalue=0,
                                                command=self.enable_entries)
        self.cb_blacklist.grid(row=2, column=0, padx=5, pady=5, sticky="nsw")

        labels_text = ("Modify words to remove:",
                       "Modify words to replace:")

        for i in range(len(labels_text)):
            label = tkinter.Label(self, text=labels_text[i], font=("Verdana", 12))
            label.grid(row=i + 3, column=0, padx=5, pady=5, sticky="nsw")

        self.cb_popup_state = tkinter.IntVar()
        self.cb_popup_state.set(0)
        self.cb_popup = tkinter.Checkbutton(self, text="Add alert with message:",
                                            variable=self.cb_popup_state,
                                            onvalue=1, offvalue=0,
                                            state=tkinter.DISABLED,
                                            command=self.enable_entries)
        self.cb_popup.grid(row=5, column=0, padx=5, pady=5, sticky="nsw")

        self.ent_host = tkinter.Entry(self)
        self.ent_host.grid(row=1, column=1, pady=5, sticky="nsw")
        self.ent_words_to_remove = tkinter.Entry(self, state=tkinter.DISABLED)
        self.ent_words_to_remove.grid(row=3, column=1, pady=5, sticky="nsw")
        self.ent_words_to_replace = tkinter.Entry(self, state=tkinter.DISABLED)
        self.ent_words_to_replace.grid(row=4, column=1, pady=5, sticky="nsw")
        self.ent_popup_text = tkinter.Entry(self, state=tkinter.DISABLED)
        self.ent_popup_text.grid(row=5, column=1, pady=5, sticky="nsew")

        self.btn_back = tkinter.Button(self, text="Back",
                                       state=tkinter.NORMAL,
                                       command=lambda: self.controller.show_frame(ConfigurationWin))
        self.btn_back.grid(row=6, column=3, padx=5, pady=5)
        self.btn_save = tkinter.Button(self, text="Save",
                                       state=tkinter.NORMAL,
                                       command=self.save_command)
        self.btn_save.grid(row=6, column=2, padx=5, pady=5)

    def enable_entries(self):  # When the site is not to be blacklisted
        if self.cb_blacklist_state.get() == 0:  # If the cb is un-checked
            self.ent_words_to_remove.config(state=tkinter.NORMAL)
            self.ent_words_to_replace.config(state=tkinter.NORMAL)
            self.cb_popup.config(state=tkinter.NORMAL)
            if self.cb_popup_state.get() == 1:
                self.ent_popup_text.config(state=tkinter.NORMAL)
            else:
                self.ent_popup_text.config(state=tkinter.DISABLED)
        else:
            self.ent_words_to_remove.config(state=tkinter.DISABLED)
            self.ent_words_to_replace.config(state=tkinter.DISABLED)
            self.cb_popup.config(state=tkinter.DISABLED)
            self.ent_popup_text.config(state=tkinter.DISABLED)

    def __check_valid_ents(self):

        if self.ent_host.get() is not "":
            if self.cb_blacklist_state.get() == 0 and self.cb_popup_state.get() == 1:
                if self.ent_popup_text.get() is "":
                    self.__mark_unvalid_ent(self.ent_popup_text)
                    return False
        else:
            self.__mark_unvalid_ent(self.ent_host)
            return False
        return True

    @staticmethod
    def __mark_unvalid_ent(ent):
        ent.config(bg="red")

    def revert(self):
        self.ent_words_to_remove.config(state=tkinter.NORMAL)
        self.ent_words_to_replace.config(state=tkinter.NORMAL)
        self.cb_popup.config(state=tkinter.NORMAL)

        self.ent_host.delete(0, tkinter.END)
        self.ent_host.config(bg="white")
        self.ent_words_to_remove.delete(0, tkinter.END)
        self.ent_words_to_replace.delete(0, tkinter.END)
        self.ent_popup_text.delete(0, tkinter.END)
        self.ent_popup_text.config(bg="white")

        self.cb_blacklist_state.set(1)
        self.cb_popup_state.set(0)

        self.ent_words_to_remove.config(state=tkinter.DISABLED)
        self.ent_words_to_replace.config(state=tkinter.DISABLED)
        self.cb_popup.config(state=tkinter.DISABLED)

    def save_command(self):
        if self.__check_valid_ents():
            #  saving relevant parameters to saved sites
            self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()] = dict()

            self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]['host'] = self.ent_host.get()

            if self.cb_blacklist_state.get() == 0:
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]['blacklist'] = False
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["words_to_remove"] = \
                    self.ent_words_to_remove.get()
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["words_to_replace"] = \
                    self.ent_words_to_replace.get()

                if self.cb_popup_state.get() == 1:
                    self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["alert_bool"] = \
                        True, self.ent_popup_text.get()
                else:
                    self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["alert_bool"] = False,
            else:
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]['blacklist'] = True
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["alert_bool"] = False,
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["words_to_remove"] = None
                self.controller.frames[ConfigurationWin].saved_sites[self.ent_host.get()]["words_to_replace"] = None

            if self.ent_host.get() not in self.controller.frames[ConfigurationWin].lb_sites.get(0, tkinter.END):
                self.controller.frames[ConfigurationWin].lb_sites.insert(tkinter.END, self.ent_host.get())
                self.controller.frames[ConfigurationWin].lb_sites.itemconfig(tkinter.END, bg='green')

            self.controller.show_frame(ConfigurationWin)

            self.revert()


class LoggingHandler(logging.Handler):  # For logging in the tkinter window
    def __init__(self, text):
        # run the regular Handler __init__
        logging.Handler.__init__(self)
        # Store a reference to the Text it will log to
        self.text = text
        self.dict_levels = {"DEBUG": "green",
                            "INFO": "black",
                            "WARNING": "yellow",
                            "ERROR": "red",
                            "CRITICAL": "red"}

    def emit(self, record):
        msg = self.format(record)
        tag = None

        for level in self.dict_levels.keys():
            self.text.tag_config(level, foreground=self.dict_levels[level])

        for level in self.dict_levels.keys():
            if level in msg:
                tag = level

        def append():
            self.text.configure(state=tkinter.NORMAL)
            self.text.insert(tkinter.END, msg + '\n', tag)
            self.text.configure(state=tkinter.DISABLED)
            self.text.yview(tkinter.END)  # Auto-scroll to the bottom

        # This is necessary because we can't modify the Text from other threads
        self.text.after(0, append)


if __name__ == '__main__':
    app = ProxyApplication()
    app.mainloop()
