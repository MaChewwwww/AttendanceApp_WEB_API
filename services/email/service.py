import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import secrets
import string
from datetime import datetime, timedelta
from .config import (
    EMAIL_SMTP_SERVER, 
    EMAIL_SMTP_PORT, 
    EMAIL_ADDRESS, 
    EMAIL_PASSWORD, 
    EMAIL_USE_TLS,
    EMAIL_VERIFICATION_SUBJECT,
    EMAIL_PASSWORD_RESET_SUBJECT,
    APP_NAME
)

class EmailService:
    def __init__(self):
        self.smtp_server = EMAIL_SMTP_SERVER
        self.smtp_port = EMAIL_SMTP_PORT
        self.email = EMAIL_ADDRESS
        self.password = EMAIL_PASSWORD
        self.use_tls = EMAIL_USE_TLS
        
    def _create_smtp_connection(self):
        """Create and return SMTP connection"""
        try:
            # Create SMTP connection
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            if self.use_tls:
                # Enable TLS encryption
                context = ssl.create_default_context()
                server.starttls(context=context)
            
            # Login to email account
            server.login(self.email, self.password)
            
            return server
        except Exception as e:
            print(f"Error creating SMTP connection: {e}")
            raise
    
    def send_email(self, to_email, subject, body_text, body_html=None, attachments=None):
        """
        Send an email
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body_text (str): Plain text body
            body_html (str, optional): HTML body
            attachments (list, optional): List of file paths to attach
            
        Returns:
            tuple: (success, message)
        """
        try:
            # Validate email configuration
            if not self.email or not self.password:
                return False, "Email credentials not configured"
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.email
            message["To"] = to_email
            
            # Add text part
            text_part = MIMEText(body_text, "plain")
            message.attach(text_part)
            
            # Add HTML part if provided
            if body_html:
                html_part = MIMEText(body_html, "html")
                message.attach(html_part)
            
            # Send email
            server = self._create_smtp_connection()
            text = message.as_string()
            server.sendmail(self.email, to_email, text)
            server.quit()
            
            print(f"Email sent successfully to {to_email}")
            return True, "Email sent successfully"
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def send_registration_otp_email(self, to_email, first_name, otp_code):
        """
        Send registration OTP email
        
        Args:
            to_email (str): Recipient email
            first_name (str): User's first name
            otp_code (str): 6-digit OTP code
            
        Returns:
            tuple: (success, message)
        """
        try:
            subject = f"{APP_NAME} - Registration Verification"
            
            # Plain text version
            body_text = f"""
Hello {first_name},

Thank you for registering with {APP_NAME}!

Your registration verification code is: {otp_code}

This code will expire in 15 minutes.

If you didn't create an account, please ignore this email.

Best regards,
{APP_NAME} Team
            """.strip()
            
            # HTML version
            body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #10B981; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .otp-code {{ 
            display: inline-block; 
            padding: 15px 25px; 
            background-color: #f0fdf4; 
            border: 2px solid #10B981;
            color: #10B981; 
            font-size: 24px;
            font-weight: bold;
            letter-spacing: 3px;
            border-radius: 8px; 
            margin: 20px 0;
        }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{APP_NAME}</h1>
        </div>
        <div class="content">
            <h2>Registration Verification</h2>
            <p>Hello {first_name},</p>
            <p>Thank you for registering with {APP_NAME}!</p>
            <p>Your registration verification code is:</p>
            <div style="text-align: center;">
                <span class="otp-code">{otp_code}</span>
            </div>
            <p><strong>This code will expire in 15 minutes.</strong></p>
            <p>If you didn't create an account, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>© 2024 {APP_NAME}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
            """.strip()
            
            return self.send_email(to_email, subject, body_text, body_html)
            
        except Exception as e:
            error_msg = f"Failed to send registration OTP email: {str(e)}"
            print(error_msg)
            return False, error_msg

    # Add placeholder methods for other OTP types to avoid errors
    def send_password_reset_otp_email(self, to_email, first_name, otp_code):
        """Placeholder for password reset OTP email"""
        return self.send_registration_otp_email(to_email, first_name, otp_code)
    
    def send_email_verification_otp_email(self, to_email, first_name, otp_code):
        """Placeholder for email verification OTP email"""
        return self.send_registration_otp_email(to_email, first_name, otp_code)
    
    def send_generic_otp_email(self, to_email, first_name, otp_code, purpose):
        """Placeholder for generic OTP email"""
        return self.send_registration_otp_email(to_email, first_name, otp_code)
