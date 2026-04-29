import tkinter as tk
from tkinter import scrolledtext, messagebox
import imaplib
import email
from email.header import decode_header
import threading

class MailCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mail Fetcher Panel")
        self.root.geometry("700x500")
        self.root.configure(padx=10, pady=10)

        # Input Frame
        self.input_frame = tk.Frame(root)
        self.input_frame.pack(fill=tk.X, pady=(0, 10))

        # FORMAT BURADA GÜNCELLENDİ
        self.lbl_format = tk.Label(self.input_frame, text="Account Data (mail:password:2fa:apppassword):", font=("Arial", 10, "bold"))
        self.lbl_format.pack(anchor=tk.W)

        self.entry_account = tk.Entry(self.input_frame, width=80, font=("Arial", 10))
        self.entry_account.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_check = tk.Button(self.input_frame, text="Check Mails", command=self.start_checking, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_check.pack(side=tk.RIGHT)

        # Status Label
        self.lbl_status = tk.Label(root, text="Waiting for input...", fg="gray", font=("Arial", 9))
        self.lbl_status.pack(anchor=tk.W)

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
            # HATA MESAJI GÜNCELLENDİ
            messagebox.showerror("Format Error", "Invalid format! Must be: mail:password:2fa:apppassword")
            return

        self.btn_check.config(state=tk.DISABLED)
        self.lbl_status.config(text="Connecting to IMAP and fetching mails...", fg="blue")
        self.text_result.delete(1.0, tk.END)

        # INDEXLER GÜNCELLENDİ: Email (Index 0) ve App Password (Index 3)
        user_email = parts[0]
        app_password = parts[3]

        threading.Thread(target=self.fetch_mails, args=(user_email, app_password), daemon=True).start()

    def fetch_mails(self, email_addr, app_pass):
        try:
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

        except imaplib.IMAP4.error:
            self.update_gui("Login Failed! Check your App Password or ensure IMAP is enabled.", "red", done=True)
        except Exception as e:
            self.update_gui(f"An error occurred: {str(e)}", "red", done=True)

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
