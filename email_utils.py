from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from email_config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.EMAIL_USERNAME,
    MAIL_PASSWORD=settings.EMAIL_PASSWORD,
    MAIL_HOST=settings.EMAIL_HOST,
    MAIL_PORT=settings.EMAIL_PORT,
    MAIL_FROM=settings.EMAIL_FROM,
    MAIL_TLS=True,
    MAIL_SSL=False
)

async def send_email(subject: str, recipient: str, body: str):
    message = MessageSchema(
        subject=subject,
        recipients=[recipient],
        body=body,
        subtype="html"
    )
    fm = FastMail(conf)
    await fm.send_message(message)