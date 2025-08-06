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
        master.title("数据广播服务器")
        master.geometry("400x320")
        
        # 按钮
        btn_frame = tk.Frame(master)
        btn_frame.pack(pady=8)

        self.add_btn   = tk.Button(btn_frame, text="添加数据", width=11, command=self.add_data)
        self.start_btn = tk.Button(btn_frame, text="Start",    width=11, command=self.start_server,  state=tk.NORMAL)
        self.stop_btn  = tk.Button(btn_frame, text="Stop",     width=11, command=self.stop_server,   state=tk.DISABLED)

        self.add_btn.grid(row=0, column=0, padx=6)
        self.start_btn.grid(row=0, column=1, padx=6)
        self.stop_btn.grid(row=0, column=2, padx=6)

        # ===== IP / Port 输入框 =====
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

        tk.Label(ip_frame, text="间隔(s):").grid(row=0, column=4, sticky='e')
        self.interval_entry = tk.Entry(ip_frame, width=5)
        self.interval_entry.insert(0, '1')
        self.interval_entry.grid(row=0, column=5)

        # 状态
        self.status_var = tk.StringVar(value="服务器未启动")
        tk.Label(master, textvariable=self.status_var).pack()
        self.fileinfo_var = tk.StringVar(value="已选文件: 0")
        tk.Label(master, textvariable=self.fileinfo_var).pack(pady=(0,4))

         # ===== 文件列表显示 =====
        list_frame = tk.Frame(master)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12)

        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(list_frame, height=7, yscrollcommand=scrollbar.set)
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # 线程与资源
        self.server = None
        self.clients = []
        self.lock = threading.Lock()
        self.running = False
        #self.threads = []

        # 已选数据文件列表
        self.data_files = []     # 保存用户选中的文件路径
    # -------------- UI 逻辑 --------------
    def add_data(self):
        """弹出文件选择对话框，让用户选择要广播的 TXT 数据文件"""
        paths = filedialog.askopenfilenames(
            title="选择要广播的数据文件",
            filetypes=[("Text Files", "*.txt")])

        if not paths:
            return

        # 去重后保存
        for p in paths:
            if p not in self.data_files:
                self.data_files.append(p)
        # 更新计数
        self.fileinfo_var.set(f"已选文件: {len(self.data_files)}")
        # 刷新列表显示
        self.refresh_file_listbox()

    def refresh_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for p in self.data_files:
            self.file_listbox.insert(tk.END, os.path.basename(p))

    # -------------- 网络逻辑 --------------
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
        print(f"[连接] 客户端 {addr}")
        try:
            while self.running:
                time.sleep(0.1)
        finally:
            with self.lock:
                if conn in self.clients:
                    self.clients.remove(conn)
            conn.close()
            print(f"[断开] 客户端 {addr}")

    def accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server.accept()
                with self.lock:
                    self.clients.append(conn)
                threading.Thread(target=self.handle_client, args=(conn,addr), daemon=True).start()
                
                #self.threads.append(t)
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
            print(f"[发送] {entry}")
            time.sleep(interval)
        self.stop_server()
    # -------------- 控制 --------------
    def start_server(self):
        # 1. 收集要广播的全部条目
        entries = []
        # (1) 用户自己添加的文件
        for f in self.data_files:
            if os.path.isfile(f):
                entries.extend(self.read_entries(f))
        # (2) 如果没有选择任何文件，则尝试读取默认 data.txt        
        if not entries:
            default_file = 'data.txt'
            if not os.path.isfile(default_file):
                messagebox.showerror("错误", "未选择数据文件，且默认 data.txt 不存在！")
                return
            entries = self.read_entries(default_file)

        if not entries:
            messagebox.showwarning("提示", "文件为空或无有效条目")
            return
        
        # 2. 校验 IP & 端口
        host = self.ip_entry.get().strip() or '0.0.0.0'
        try:
            ipaddress.ip_address(host)
        except ValueError:
            messagebox.showerror("错误", "IP 格式不合法")
            return

        try:
            port = int(self.port_entry.get())
            if not (0 < port < 65536):
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "端口必须是 1~65535 的整数")
            return
        # ---------- 解析间隔 ----------
        try:
            interval = float(self.interval_entry.get())
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "间隔必须是大于 0 的数字")
            return
        
        # 3. 创建并绑定套接字
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server.bind((host, port))
            self.server.listen(5)
        except Exception as e:
            self.server.close()
            messagebox.showerror("错误", f"端口占用或启动失败：\n{e}")
            return

        self.running = True

        # 接收&# 广播线程
        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.broadcast_loop, args=(entries, interval), daemon=True).start()
        
        # ---------- 更新 UI ----------
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.add_btn.config(state=tk.DISABLED)
        self.status_var.set(f"运行中: {host}:{port}  |  间隔 {interval}s")
        print(f"[启动] 服务器监听 {host}:{port}, 间隔 {interval}s")

    def stop_server(self):
        if not self.running:
            return
        self.running = False
        # 关闭监听 socket
        try:
            self.server.close()
        except:
            pass
        # 断开所有客户端
        with self.lock:
            for c in list(self.clients):
                try:
                    c.shutdown(socket.SHUT_RDWR)
                    c.close()
                except:
                    pass
            self.clients.clear()

         # UI 复位
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.add_btn.config(state=tk.NORMAL)
        self.status_var.set("已停止")
        print("[停止] 服务器已关闭")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()
