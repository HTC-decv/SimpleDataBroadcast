import socket
import threading
import time
import os
import ipaddress
import sys
import tkinter as tk
from tkinter import messagebox, filedialog, Scrollbar

class ServerApp:
    def __init__(self, master):
        self.master = master
        master.title("Data broadcast server")
        master.geometry("400x320")
        
        # =============Buttons==============
        btn_frame = tk.Frame(master)
        btn_frame.pack(pady=8)

        self.add_btn   = tk.Button(btn_frame, text="Add File", width=11, command=self.add_data)
        self.start_btn = tk.Button(btn_frame, text="Start",    width=11, command=self.start_server,  state=tk.NORMAL)
        self.stop_btn  = tk.Button(btn_frame, text="Stop",     width=11, command=self.stop_server,   state=tk.DISABLED)

        self.add_btn.grid(row=0, column=0, padx=6)
        self.start_btn.grid(row=0, column=1, padx=6)
        self.stop_btn.grid(row=0, column=2, padx=6)

        # ===== IP / Port / interval Input box =====
        ip_frame = tk.Frame(master)
        ip_frame.pack(pady=4)

        tk.Label(ip_frame, text="IP:").grid(row=0, column=0, sticky='e')
        self.ip_entry = tk.Entry(ip_frame, width=12)
        self.ip_entry.insert(0, '0.0.0.0')
        self.ip_entry.grid(row=0, column=1, padx=(0,15))

        tk.Label(ip_frame, text="Port:").grid(row=0, column=2, sticky='e')
        self.port_entry = tk.Entry(ip_frame, width=7)
        self.port_entry.insert(0, '1000')
        self.port_entry.grid(row=0, column=3, padx=(0,15))

        tk.Label(ip_frame, text="Interval(s):").grid(row=0, column=4, sticky='e')
        self.interval_entry = tk.Entry(ip_frame, width=5)
        self.interval_entry.insert(0, '1')
        self.interval_entry.grid(row=0, column=5)

        # =========== Status bar ================
        self.status_var = tk.StringVar(value="The server is not started")
        tk.Label(master, textvariable=self.status_var).pack()
        self.fileinfo_var = tk.StringVar(value="Selected file: 0")
        tk.Label(master, textvariable=self.fileinfo_var).pack(pady=(0,4))

         # ===== File list display ===========
        list_frame = tk.Frame(master)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12)

        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(list_frame, height=7, yscrollcommand=scrollbar.set)
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # ======= Threads and resources ===========
        self.server = None
        self.clients = []
        self.lock = threading.Lock()
        self.running = False
        #self.threads = []

        # Selected data file list
        self.data_files = []     # Save the file paths selected by the user
    # -------------- UI  --------------
    def add_data(self):
        """Pop up a file selection dialog to let the user choose the TXT data file(s) to broadcast."""
        paths = filedialog.askopenfilenames(
            title="Select the data file(s) to broadcast",
            filetypes=[("Text Files", "*.txt")])

        if not paths:
            return

        # Save after removing duplicates
        for p in paths:
            if p not in self.data_files:
                self.data_files.append(p)
        # Update count
        self.fileinfo_var.set(f"Selected file(s): {len(self.data_files)}")
        # Refresh list display
        self.refresh_file_listbox()

    def refresh_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for p in self.data_files:
            self.file_listbox.insert(tk.END, os.path.basename(p))

    # ================== Network logic ==============
    @staticmethod
    def read_entries( filepath):
        entries = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(line)
        return entries

    def handle_client(self, conn, addr):
        print(f"[Connect] Client {addr}")
        try:
            while self.running:
                time.sleep(0.1)
        finally:
            with self.lock:
                if conn in self.clients:
                    self.clients.remove(conn)
            conn.close()
            print(f"[Disconnect] Client {addr}")

    def accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server.accept()
                with self.lock:
                    self.clients.append(conn)
                threading.Thread(target=self.handle_client, args=(conn,addr), daemon=True).start()
                
            except:
                break

    def broadcast_loop(self, entries, interval):
        for entry in entries:
            if not self.running:
                break
            with self.lock:
                for c in list(self.clients):
                    try:
                        c.sendall(entry.encode('utf-8'))
                    except:
                        pass
            print(f"[Send] {entry}")
            time.sleep(interval)
        self.stop_server()
    # ==================- Control ================
    def start_server(self):
        # 1. Collect all entries to be broadcast
        entries = []
        # (1) User-added files
        for f in self.data_files:
            if os.path.isfile(f):
                entries.extend(self.read_entries(f))
        # (2) If no file is selected, try to read the default data.txt.       
        if not entries:
            default_file = 'data.txt'
            if not os.path.isfile(default_file):
                messagebox.showerror("Error", "No data file selected, and the default data.txt does not exist!")
                return
            entries = self.read_entries(default_file)

        if not entries:
            messagebox.showwarning("Notice", "The file is empty or contains no valid entries.")
            return
        
        # 2. Validate IP & port
        host = self.ip_entry.get().strip() or '0.0.0.0'
        try:
            ipaddress.ip_address(host)
        except ValueError:
            messagebox.showerror("Error", "Invalid IP format")
            return

        try:
            port = int(self.port_entry.get())
            if not (0 < port < 65536):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Port must be an integer between 1 and 65535")
            return
        # ================= Parse interval ===================
        try:
            interval = float(self.interval_entry.get())
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Interval must be a number greater than 0")
            return
        
        # 3. Create and bind socket
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server.bind((host, port))
            self.server.listen(5)
        except Exception as e:
            self.server.close()
            messagebox.showerror("Error", f"Port is in use or failed to start:\n{e}")
            return

        self.running = True

        # Receive &# Broadcast Thread
        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.broadcast_loop, args=(entries, interval), daemon=True).start()
        
        # =============== Update UI ==================
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.add_btn.config(state=tk.DISABLED)
        self.status_var.set(f"Running: {host}:{port}  |  Interval {interval}s")
        print(f"[Started] Server listening on {host}:{port}, interval {interval}s")

    def stop_server(self):
        if not self.running:
            return
        self.running = False
        # Close listening socket
        try:
            self.server.close()
        except:
            pass
        # Disconnect all clients
        with self.lock:
            for c in list(self.clients):
                try:
                    c.shutdown(socket.SHUT_RDWR)
                    c.close()
                except:
                    pass
            self.clients.clear()

         # Disconnect all clients
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.add_btn.config(state=tk.NORMAL)
        self.status_var.set("Stopped")
        print("[Stopped] Server has been closed")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()
