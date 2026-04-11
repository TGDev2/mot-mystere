from tkinter import filedialog, messagebox


class NullDialogPort:
    def show_error(self, _title, _message):
        return None

    def show_info(self, _title, _message):
        return None

    def ask_yes_no(self, _title, _message):
        return False


class NullFileDialogPort:
    def ask_open_filename(self, **_kwargs):
        return ""

    def ask_directory(self, **_kwargs):
        return ""

    def ask_save_as_filename(self, **_kwargs):
        return ""


class NullTimerPort:
    def schedule(self, _delay_ms, _callback):
        return None

    def cancel(self, _job):
        return None


class TkDialogPort:
    def show_error(self, title, message):
        return messagebox.showerror(title, message)

    def show_info(self, title, message):
        return messagebox.showinfo(title, message)

    def ask_yes_no(self, title, message):
        return messagebox.askyesno(title, message)


class TkFileDialogPort:
    def ask_open_filename(self, **kwargs):
        return filedialog.askopenfilename(**kwargs)

    def ask_directory(self, **kwargs):
        return filedialog.askdirectory(**kwargs)

    def ask_save_as_filename(self, **kwargs):
        return filedialog.asksaveasfilename(**kwargs)


class TkTimerPort:
    def __init__(self, root):
        self.root = root

    def schedule(self, delay_ms, callback):
        return self.root.after(delay_ms, callback)

    def cancel(self, job):
        return self.root.after_cancel(job)
