from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import settings
import logging

logger = logging.getLogger(__name__)

async def send_email(to: str, subject: str, body: str):
    """
    Send an email using SendGrid
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (HTML or plain text)
    """
    if not settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY is not set. Email will not be sent.")
        return False

    message = Mail(
        from_email=settings.EMAIL_FROM,
        to_emails=to,
        subject=subject,
        html_content=body
    )

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code in [200, 202]:
            logger.info(f"Email sent successfully to {to}")
            return True
        else:
            logger.error(f"Failed to send email. Status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False
