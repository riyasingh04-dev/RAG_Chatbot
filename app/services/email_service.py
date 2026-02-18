import aiosmtplib
from email.message import EmailMessage
from app.core.config import settings
from loguru import logger
import random

class EmailService:
    @staticmethod
    async def send_otp(email: str, otp: str):
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(f"SMTP not configured. OTP for {email} is: {otp}")
            return True

        message = EmailMessage()
        message["From"] = settings.EMAILS_FROM
        message["To"] = email
        message["Subject"] = "Your Enterprise AI Chatbot OTP"
        message.set_content(f"Your verification code is: {otp}\nThis code will expire in 10 minutes.")

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=True if settings.SMTP_PORT == 465 else False,
                start_tls=True if settings.SMTP_PORT == 587 else False,
            )
            logger.info(f"OTP sent successfully to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    @staticmethod
    def generate_otp():
        return "".join([str(random.randint(0, 9)) for _ in range(6)])

email_service = EmailService()
