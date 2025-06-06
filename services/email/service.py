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

    def send_welcome_email(self, to_email, first_name):
        """
        Send welcome email after successful verification
        
        Args:
            to_email (str): Recipient email
            first_name (str): User's first name
            
        Returns:
            tuple: (success, message)
        """
        try:
            subject = f"Welcome to AttendanceApp!"
            
            # Plain text version
            body_text = f"""
Hello {first_name},

Welcome to AttendanceApp! Your account has been successfully verified.

You can now:
- Submit attendance using face recognition
- View your attendance history
- Track your attendance analytics

Thank you for joining us!

Best regards,
AttendanceApp Team
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
        .feature {{ padding: 10px; margin: 10px 0; background-color: white; border-radius: 5px; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to AttendanceApp!</h1>
        </div>
        <div class="content">
            <h2>Hello {first_name},</h2>
            <p>Congratulations! Your account has been successfully verified and is now active.</p>
            
            <h3>What you can do now:</h3>
            <div class="feature">
                <strong>📸 Face Recognition Attendance</strong><br>
                Submit your attendance quickly and securely using face recognition technology.
            </div>
            <div class="feature">
                <strong>📊 Attendance History</strong><br>
                View and track your attendance records over time.
            </div>
            <div class="feature">
                <strong>📈 Analytics Dashboard</strong><br>
                Get insights into your attendance patterns and performance.
            </div>
            
            <p>Thank you for choosing AttendanceApp. We're excited to have you on board!</p>
        </div>
        <div class="footer">
            <p>© 2024 AttendanceApp. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
            """.strip()
            
            return self.send_email(to_email, subject, body_text, body_html)
            
        except Exception as e:
            error_msg = f"Failed to send welcome email: {str(e)}"
            print(error_msg)
            return False, error_msg

    def send_login_otp_email(self, to_email, first_name, otp_code):
        """
        Send login OTP email
        
        Args:
            to_email (str): Recipient email
            first_name (str): User's first name
            otp_code (str): 6-digit OTP code
            
        Returns:
            tuple: (success, message)
        """
        try:
            subject = f"{APP_NAME} - Login Verification"
            
            # Plain text version
            body_text = f"""
Hello {first_name},

Your login verification code is: {otp_code}

This code will expire in 15 minutes.

If you didn't try to log in, please ignore this email.

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
            <h2>Login Verification</h2>
            <p>Hello {first_name},</p>
            <p>Your login verification code is:</p>
            <div style="text-align: center;">
                <span class="otp-code">{otp_code}</span>
            </div>
            <p><strong>This code will expire in 15 minutes.</strong></p>
            <p>If you didn't try to log in, please ignore this email.</p>
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
            error_msg = f"Failed to send login OTP email: {str(e)}"
            print(error_msg)
            return False, error_msg

    def send_password_reset_otp_email(self, to_email, first_name, otp_code):
        """
        Send password reset OTP email
        
        Args:
            to_email (str): Recipient email
            first_name (str): User's first name
            otp_code (str): 6-digit OTP code
            
        Returns:
            tuple: (success, message)
        """
        try:
            subject = f"{APP_NAME} - Password Reset Verification"
            
            # Plain text version
            body_text = f"""
Hello {first_name},

Your password reset verification code is: {otp_code}

This code will expire in 15 minutes.

If you didn't request a password reset, please ignore this email.

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
        .header {{ background-color: #EF4444; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .otp-code {{ 
            display: inline-block; 
            padding: 15px 25px; 
            background-color: #fef2f2; 
            border: 2px solid #EF4444;
            color: #EF4444; 
            font-size: 24px;
            font-weight: bold;
            letter-spacing: 3px;
            border-radius: 8px; 
            margin: 20px 0;
        }}
        .warning {{ 
            background-color: #fef3cd; 
            border: 1px solid #ffc107; 
            padding: 10px; 
            border-radius: 5px; 
            margin: 15px 0;
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
            <h2>Password Reset Verification</h2>
            <p>Hello {first_name},</p>
            <p>Your password reset verification code is:</p>
            <div style="text-align: center;">
                <span class="otp-code">{otp_code}</span>
            </div>
            <p><strong>This code will expire in 15 minutes.</strong></p>
            <div class="warning">
                <strong>Security Notice:</strong> If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
            </div>
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
            error_msg = f"Failed to send password reset OTP email: {str(e)}"
            print(error_msg)
            return False, error_msg

    def send_password_reset_success_email(self, to_email, first_name):
        """
        Send password reset success email
        
        Args:
            to_email (str): Recipient email
            first_name (str): User's first name
            
        Returns:
            tuple: (success, message)
        """
        try:
            subject = f"{APP_NAME} - Password Reset Successful"
            
            # Plain text version
            body_text = f"""
Hello {first_name},

Your password has been successfully reset for your {APP_NAME} account.

If you did not make this change, please contact support immediately.

You can now log in with your new password.

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
        .success-message {{ 
            background-color: #d1fae5; 
            border: 1px solid #10B981; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 15px 0;
            text-align: center;
        }}
        .warning {{ 
            background-color: #fef3cd; 
            border: 1px solid #ffc107; 
            padding: 10px; 
            border-radius: 5px; 
            margin: 15px 0;
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
            <h2>Password Reset Successful</h2>
            <p>Hello {first_name},</p>
            
            <div class="success-message">
                <strong>✅ Your password has been successfully reset!</strong>
            </div>
            
            <p>Your {APP_NAME} account password has been updated. You can now log in with your new password.</p>
            
            <div class="warning">
                <strong>Security Notice:</strong> If you did not make this change, please contact our support team immediately.
            </div>
            
            <p>Thank you for using {APP_NAME}!</p>
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
            error_msg = f"Failed to send password reset success email: {str(e)}"
            print(error_msg)
            return False, error_msg

    # Add placeholder methods for other OTP types to avoid errors
    def send_email_verification_otp_email(self, to_email, first_name, otp_code):
        """Placeholder for email verification OTP email"""
        return self.send_registration_otp_email(to_email, first_name, otp_code)
    
    def send_generic_otp_email(self, to_email, first_name, otp_code, purpose):
        """Placeholder for generic OTP email"""
        return self.send_registration_otp_email(to_email, first_name, otp_code)
