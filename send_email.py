import os
import sys
import ssl
import smtplib
from email.message import EmailMessage


def send_email(
    smtp_server: str,
    smtp_port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
        server.login(username, password)
        server.send_message(message)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python send_email.py recipient@example.com "
              "\"Subject\" \"Message body\"")
        print("Vous pouvez définir les variables d'environnement EMAIL_USER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT.")
        sys.exit(1)

    recipient = sys.argv[1]
    subject = sys.argv[2]
    body = sys.argv[3]

    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    username = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")

    if not username or not password:
        print("Erreur : définissez EMAIL_USER et EMAIL_PASSWORD dans l'environnement.")
        sys.exit(1)

    sender = username

    try:
        send_email(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=username,
            password=password,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
        )
        print(f"E-mail envoyé à {recipient}.")
    except Exception as exc:
        print(f"Erreur lors de l'envoi de l'e-mail : {exc}")
        sys.exit(1)
