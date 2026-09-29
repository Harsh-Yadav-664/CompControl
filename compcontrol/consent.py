"""Fail-closed native consent, separate from browser JavaScript and AI prose."""
import time


def native_confirm(title, detail, valid, parent=None):
    import tkinter as tk
    if parent is not None:
        import threading
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('Parented consent must run on the Tk main thread.')
    root = tk.Toplevel(parent) if parent is not None else tk.Tk()
    root.title(title)
    root.geometry('600x420')
    root.minsize(480, 340)
    root.configure(bg='#161923')
    root.attributes('-topmost', True)
    if parent is not None:
        root.transient(parent)
    approved = False
    closed = False
    timer = None
    ready = time.monotonic() + 1

    def close():
        nonlocal closed
        if closed:
            return
        closed = True
        if timer is not None:
            root.after_cancel(timer)
        root.destroy()

    def still_valid():
        try:
            return valid()
        except Exception:
            return False

    def allow():
        nonlocal approved
        approved = time.monotonic() >= ready and still_valid()
        close()

    tk.Label(root, text='Allow this one desktop action?', bg='#161923', fg='#f1f2f7',
             font=('Segoe UI', 16, 'bold'), anchor='w').pack(fill='x', padx=24, pady=(24, 14))
    text = tk.Text(root, wrap='word', bg='#222635', fg='#edf0f7', relief='flat',
                   font=('Segoe UI', 10), padx=12, pady=12, height=8)
    text.insert('1.0', detail)
    text.configure(state='disabled')
    text.pack(fill='both', expand=True, padx=24)
    tk.Label(root, text='Review the exact destination. This does not grant administrator access.',
             bg='#161923', fg='#b8bed1', font=('Segoe UI', 9), wraplength=510, anchor='w').pack(
                 fill='x', padx=24, pady=12)
    row = tk.Frame(root, bg='#161923')
    row.pack(fill='x', padx=24, pady=(0, 22))
    deny = tk.Button(row, text='Cancel', command=close, width=14,
                     bg='#303649', fg='#f1f2f7', relief='flat', padx=10, pady=8)
    deny.pack(side='right')
    permit = tk.Button(row, text='Allow once', command=allow, state='disabled', width=14,
                       bg='#b6a6ff', fg='#171324', relief='flat', padx=10, pady=8)
    permit.pack(side='right', padx=(0, 10))
    root.protocol('WM_DELETE_WINDOW', close)
    root.bind('<Return>', lambda _: close())
    root.bind('<Escape>', lambda _: close())
    deny.focus_set()

    def check():
        nonlocal timer
        timer = None
        if not still_valid():
            close()
            return
        if time.monotonic() >= ready:
            permit.configure(state='normal')
        timer = root.after(150, check)

    timer = root.after(150, check)
    try:
        if parent is not None:
            root.grab_set()
            parent.wait_window(root)
        else:
            root.mainloop()
    finally:
        try:
            close()
        except tk.TclError:
            pass
    return approved
