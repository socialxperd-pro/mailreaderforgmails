import tkinter as tk
from tkinter import scrolledtext, messagebox
import imaplib
import email
from email.header import decode_header
import threading
import socket
import random
import os

# Standart bağlantıyı yedekliyoruz
_original_socket = socket.socket

# PySocks kütüphanesini kontrol ediyoruz
try:
    import socks
except ImportError:
    socks = None

class MailCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mail Fetcher Panel (Random Proxy from TXT)")
        self.root.geometry("750x550")
        self.root.configure(padx=10, pady=10)

        # Otomatik olarak proxies.txt dosyasını oluştur (eğer yoksa)
        if not os.path.exists("proxies.txt"):
            open("proxies.txt", "w").close()

        # Input Frame
        self.input_frame = tk.Frame(root)
        self.input_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_format = tk.Label(self.input_frame, text="Account Data (mail:password:2fa:apppassword):", font=("Arial", 10, "bold"))
        self.lbl_format.pack(anchor=tk.W)

        self.entry_account = tk.Entry(self.input_frame, font=("Arial", 10))
        self.entry_account.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_check = tk.Button(self.input_frame, text="Check Mails", command=self.start_checking, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=12)
        self.btn_check.pack(side=tk.RIGHT)

        # Status Label
        self.lbl_status = tk.Label(root, text="Waiting... (Proxies will be loaded automatically from proxies.txt)", fg="gray", font=("Arial", 9, "bold"))
        self.lbl_status.pack(anchor=tk.W, pady=(5, 0))

        # Results Area
        self.text_result = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
        self.text_result.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def start_checking(self):
        account_data = self.entry_account.get().strip()
        
        if not account_data:
            messagebox.showwarning("Input Error", "Please enter account details.")
            return

        parts = account_data.split(':')
        if len(parts) != 4:
            messagebox.showerror("Format Error", "Invalid account format! Must be: mail:password:2fa:apppassword")
            return

        # Proxies.txt'yi oku ve rastgele seç
        proxy_to_use = None
        if os.path.exists("proxies.txt"):
            with open("proxies.txt", "r") as f:
                # Boşlukları temizle ve sadece dolu satırları listeye ekle
                proxies = [line.strip() for line in f if line.strip()]
            
            if proxies:
                proxy_to_use = random.choice(proxies)
                p_parts = proxy_to_use.split(':')
                if len(p_parts) != 4:
                    messagebox.showerror("Proxy Format Error", f"Invalid proxy format in txt!\n{proxy_to_use}\nMust be: IP:PORT:ID:PASS")
                    return
                if socks is None:
                    messagebox.showerror("Missing Library", "PySocks is not installed!\nPlease open terminal and run:\npip install pysocks")
                    return

        self.btn_check.config(state=tk.DISABLED)
        
        # Kullanıcıya hangi durumun aktif olduğunu göster
        if proxy_to_use:
            ip_address = proxy_to_use.split(':')[0]
            self.lbl_status.config(text=f"Connecting via random proxy ({ip_address})...", fg="blue")
        else:
            self.lbl_status.config(text="proxies.txt is empty. Connecting directly (NO PROXY)...", fg="blue")
            
        self.text_result.delete(1.0, tk.END)

        user_email = parts[0]
        app_password = parts[3]

        threading.Thread(target=self.fetch_mails, args=(user_email, app_password, proxy_to_use), daemon=True).start()

    def fetch_mails(self, email_addr, app_pass, proxy_data):
        try:
            # Proxy varsa tünelle, yoksa standart bağlantıyı kullan
            if proxy_data:
                ip, port, user, pw = proxy_data.split(':')
                socks.set_default_proxy(socks.HTTP, ip, int(port), True, user, pw)
                socket.socket = socks.socksocket
            else:
                socket.socket = _original_socket

            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_addr, app_pass)
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            mail_ids = messages[0].split()

            if not mail_ids:
                self.update_gui("No emails found in the inbox.", "green", done=True)
                return

            latest_email_ids = mail_ids[-5:]
            latest_email_ids.reverse()

            result_text = ""
            for i, email_id in enumerate(latest_email_ids):
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    try:
                                        body = part.get_payload(decode=True).decode()
                                    except:
                                        pass
                                    break 
                        else:
                            try:
                                body = msg.get_payload(decode=True).decode()
                            except:
                                pass

                        result_text += f"[{i+1}] SUBJECT: {subject}\n"
                        result_text += f"{'-'*50}\n"
                        result_text += f"{body.strip()}\n"
                        result_text += f"{'='*50}\n\n"

            mail.logout()
            self.update_gui(result_text, "green", done=True)

        except Exception as e:
            self.update_gui(f"Error: {str(e)}\n(Check your App Password, Proxy, or IMAP settings)", "red", done=True)
        finally:
            # İşlem bitince orijinal bağlantı ayarlarına geri dön
            socket.socket = _original_socket

    def update_gui(self, text, status_color, done=False):
        self.root.after(0, self._safe_update_gui, text, status_color, done)

    def _safe_update_gui(self, text, status_color, done):
        if done:
            self.lbl_status.config(text="Operation completed." if status_color == "green" else "Operation failed.", fg=status_color)
            self.btn_check.config(state=tk.NORMAL)
            
            if status_color == "green":
                self.text_result.insert(tk.END, text)
            else:
                messagebox.showerror("Error", text)

if __name__ == "__main__":
    root = tk.Tk()
    app = MailCheckerApp(root)
    root.mainloop()
