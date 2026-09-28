"""Native local consent, separate from browser JavaScript. No keyboard approval shortcut."""
import time


def native_confirm(title, detail, valid):
    # tkinter is bundled with standard Windows Python and included by PyInstaller.
    # No hidden worker may approve this. Closing, Escape and Return all deny.
    import tkinter as tk
    root = tk.Tk()
    root.title(title)
    root.geometry('580x390')
    root.minsize(480, 320)
    root.configure(bg='#141c16')
    root.attributes('-topmost', True)
    approved = False
    ready = time.monotonic() + 1
    label = tk.Label(root, text='Allow this one desktop action?', bg='#141c16', fg='#dcebcf',
                     font=('Segoe UI', 16, 'bold'), anchor='w')
    label.pack(fill='x', padx=24, pady=(24, 14))
    text = tk.Text(root, wrap='word', bg='#1d281d', fg='#e7ede1', relief='flat',
                   font=('Segoe UI', 10), padx=12, pady=12, height=8)
    text.insert('1.0', detail)
    text.configure(state='disabled')
    text.pack(fill='both', expand=True, padx=24)
    status = tk.Label(root, text='Review the exact destination. This is not a request for administrator access.',
                      bg='#141c16', fg='#a5b399', font=('Segoe UI', 9), wraplength=510, anchor='w')
    status.pack(fill='x', padx=24, pady=12)
    row = tk.Frame(root, bg='#141c16')
    row.pack(fill='x', padx=24, pady=(0, 22))

    def allow():
        nonlocal approved
        if time.monotonic() >= ready and valid():
            approved = True
        root.destroy()

    deny = tk.Button(row, text='Cancel', command=root.destroy, width=14,
                     bg='#293627', fg='#eff5e9', relief='flat', padx=10, pady=8)
    deny.pack(side='right')
    permit = tk.Button(row, text='Allow once', command=allow, state='disabled', width=14,
                       bg='#c5e99a', fg='#192318', relief='flat', padx=10, pady=8)
    permit.pack(side='right', padx=(0, 10))
    root.bind('<Return>', lambda _: root.destroy())
    root.bind('<Escape>', lambda _: root.destroy())
    # No mnemonic such as Y accepts the request. Cancel owns initial focus.
    deny.focus_set()

    def check():
        if not valid():
            root.destroy()
            return
        if time.monotonic() >= ready:
            permit.configure(state='normal')
        root.after(150, check)

    root.after(150, check)
    try:
        root.mainloop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
    return approved
