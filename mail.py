import tkinter as tk
from tkinter import scrolledtext, messagebox
import imaplib
import email
from email.header import decode_header
import threading
import socket

# Standart bağlantıyı yedekliyoruz (proxy'siz girişler için)
_original_socket = socket.socket

# PySocks kütüphanesini kontrol ediyoruz
try:
    import socks
except ImportError:
    socks = None

class MailCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mail Fetcher Panel v2 (Proxy Supported)")
        self.root.geometry("750x600")
        self.root.configure(padx=10, pady=10)

        # Account Input Frame
        self.input_frame = tk.Frame(root)
        self.input_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_format = tk.Label(self.input_frame, text="Account Data (mail:password:2fa:apppassword):", font=("Arial", 10, "bold"))
        self.lbl_format.pack(anchor=tk.W)

        self.entry_account = tk.Entry(self.input_frame, font=("Arial", 10))
        self.entry_account.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_check = tk.Button(self.input_frame, text="Check Mails", command=self.start_checking, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=12)
        self.btn_check.pack(side=tk.RIGHT)

        # Proxy Input Frame
        self.proxy_frame = tk.Frame(root)
        self.proxy_frame.pack(fill=tk.X, pady=(0, 15))

        self.lbl_proxy = tk.Label(self.proxy_frame, text="Proxy (ip:port:user:pw) [Optional]:", font=("Arial", 10, "bold"))
        self.lbl_proxy.pack(anchor=tk.W)

        self.entry_proxy = tk.Entry(self.proxy_frame, font=("Arial", 10))
        self.entry_proxy.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_test_proxy = tk.Button(self.proxy_frame, text="Check Proxy", command=self.start_proxy_test, bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=12)
        self.btn_test_proxy.pack(side=tk.RIGHT)

        # Status Label
        self.lbl_status = tk.Label(root, text="Waiting for input...", fg="gray", font=("Arial", 9, "bold"))
        self.lbl_status.pack(anchor=tk.W)

        # Results Area
        self.text_result = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
        self.text_result.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def start_proxy_test(self):
        proxy_data = self.entry_proxy.get().strip()
        if not proxy_data:
            messagebox.showwarning("Proxy Error", "Please enter proxy details first.")
            return

        parts = proxy_data.split(':')
        if len(parts) != 4:
            messagebox.showerror("Format Error", "Invalid proxy format! Must be: ip:port:user:pw")
            return

        if socks is None:
            messagebox.showerror("Missing Library", "PySocks is not installed!\nPlease open terminal and run:\npip install pysocks")
            return

        self.btn_test_proxy.config(state=tk.DISABLED)
        self.btn_check.config(state=tk.DISABLED)
        self.lbl_status.config(text="Testing proxy connection to Gmail servers...", fg="blue")

        threading.Thread(target=self.test_proxy_thread, args=(parts,), daemon=True).start()

    def test_proxy_thread(self, parts):
        ip, port, user, pw = parts
        try:
            # Sadece bağlanabilirliği test etmek için sanal bir soket oluşturuyoruz
            s = socks.socksocket()
            s.set_proxy(socks.HTTP, ip, int(port), True, user, pw)
            s.settimeout(10)
            
            # Gmail IMAP portuna (993) bağlanmayı deniyoruz
            s.connect(("imap.gmail.com", 993))
            s.close()
            
            self.root.after(0, self._finish_proxy_test, True, "Proxy is WORKING! Connection to Gmail is successful.")
        except Exception as e:
            self.root.after(0, self._finish_proxy_test, False, f"Proxy Failed: {str(e)}")

    def _finish_proxy_test(self, success, message):
        self.btn_test_proxy.config(state=tk.NORMAL)
        self.btn_check.config(state=tk.NORMAL)
        if success:
            self.lbl_status.config(text=message, fg="green")
            messagebox.showinfo("Proxy Success", message)
        else:
            self.lbl_status.config(text="Proxy test failed.", fg="red")
            messagebox.showerror("Proxy Error", message)

    def start_checking(self):
        account_data = self.entry_account.get().strip()
        proxy_data = self.entry_proxy.get().strip()
        
        if not account_data:
            messagebox.showwarning("Input Error", "Please enter account details.")
            return

        parts = account_data.split(':')
        if len(parts) != 4:
            messagebox.showerror("Format Error", "Invalid account format! Must be: mail:password:2fa:apppassword")
            return

        if proxy_data:
            p_parts = proxy_data.split(':')
            if len(p_parts) != 4:
                messagebox.showerror("Proxy Format Error", "Invalid proxy format! Must be: ip:port:user:pw")
                return
            if socks is None:
                messagebox.showerror("Missing Library", "PySocks is not installed!\nPlease open terminal and run:\npip install pysocks")
                return

        self.btn_check.config(state=tk.DISABLED)
        self.btn_test_proxy.config(state=tk.DISABLED)
        self.lbl_status.config(text="Connecting and fetching mails...", fg="blue")
        self.text_result.delete(1.0, tk.END)

        user_email = parts[0]
        app_password = parts[3]

        threading.Thread(target=self.fetch_mails, args=(user_email, app_password, proxy_data), daemon=True).start()

    def fetch_mails(self, email_addr, app_pass, proxy_data):
        try:
            # Eğer proxy varsa, tüm sistemi o proxy üzerinden çıkacak şekilde ayarlıyoruz
            if proxy_data:
                ip, port, user, pw = proxy_data.split(':')
                socks.set_default_proxy(socks.HTTP, ip, int(port), True, user, pw)
                socket.socket = socks.socksocket
            else:
                socket.socket = _original_socket # Proxy yoksa standart interneti kullan

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
            # İşlem bitince veya hata verince diğer bağlantıları bozmamak için soketi sıfırlıyoruz
            socket.socket = _original_socket

    def update_gui(self, text, status_color, done=False):
        self.root.after(0, self._safe_update_gui, text, status_color, done)

    def _safe_update_gui(self, text, status_color, done):
        if done:
            self.lbl_status.config(text="Operation completed." if status_color == "green" else "Operation failed.", fg=status_color)
            self.btn_check.config(state=tk.NORMAL)
            self.btn_test_proxy.config(state=tk.NORMAL)
            
            if status_color == "green":
                self.text_result.insert(tk.END, text)
            else:
                messagebox.showerror("Error", text)

if __name__ == "__main__":
    root = tk.Tk()
    app = MailCheckerApp(root)
    root.mainloop()
