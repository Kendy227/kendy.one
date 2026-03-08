import smtplib
from email.message import EmailMessage
from datetime import datetime

SMTP_HOST = 'mail.kendyenterprises.one'
SMTP_PORT = 465
SMTP_USER = 'noreply@kendyenterprises.one'
SMTP_PASS = 'Renedy@123'
ADMIN_EMAIL = 'renedysanasam13@gmail.com'
SITE_URL = 'https://kendyenterprises.one'

def send_email_with_template(to_email, subject, html_content):
    """Helper function to send emails with HTML content"""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg.set_content("Please view this email in an HTML capable client")
    msg.add_alternative(html_content, subtype='html')
    
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

def get_user_order_template(username, order_id, product_name, userid, zoneid, amount, payment_type, region):
    """Generate HTML template for user order confirmation"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Order Confirmation</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
            body {{
                font-family: 'Poppins', Arial, sans-serif;
                background-color: #0f172a;
                color: #e2e8f0;
                margin: 0;
                padding: 20px;
            }}
            .email-container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #1e293b;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }}
            .header {{
                background-color: #38bdf8;
                color: #0f172a;
                padding: 30px 20px;
                text-align: center;
            }}
            .content {{
                padding: 30px;
            }}
            .order-details {{
                margin: 20px 0;
                border: 1px solid #334155;
                border-radius: 8px;
            }}
            .detail-item {{
                display: flex;
                justify-content: space-between;
                padding: 15px 20px;
                border-bottom: 1px solid #334155;
            }}
            .detail-item:last-child {{
                border-bottom: none;
            }}
            .label {{
                color: #94a3b8;
                font-weight: 600;
            }}
            .value {{
                color: #f8fafc;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #64748b;
                font-size: 14px;
            }}
            .footer a {{
                color: #38bdf8;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>Order Confirmation</h1>
            </div>
            <div class="content">
                <p>Hi {username},</p>
                <p>Thank you for your purchase! Here are your order details:</p>
                
                <div class="order-details">
                    <div class="detail-item">
                        <span class="label">Order ID:</span>
                        <span class="value">{order_id}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">Product:</span>
                        <span class="value">{product_name} ({region})</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">User ID:</span>
                        <span class="value">{userid}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">Zone ID:</span>
                        <span class="value">{zoneid or '-'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="label">Amount:</span>
                        <span class="value">₹{amount} ({payment_type})</span>
                    </div>
                </div>

                <p>If you have any questions about your order, please contact our support team.</p>
                <p>Best regards,<br>Kendy Enterprises Team</p>
            </div>
            <div class="footer">
                © {datetime.now().year} Kendy Enterprises. All rights reserved.<br>
                <a href="{SITE_URL}/privacy-policy">Privacy Policy</a>
            </div>
        </div>
    </body>
    </html>
    """

def get_admin_order_template(order_id, username, user_email, product_name, userid, zoneid, amount, payment_type, region):
    """Generate HTML template for admin order notification"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Order Notification</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
            body {{
                font-family: 'Poppins', Arial, sans-serif;
                background-color: #0f172a;
                color: #e2e8f0;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #1e293b;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }}
            .header {{
                background-color: #38bdf8;
                color: #0f172a;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                padding: 30px;
            }}
            .order-details {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            .order-details th, .order-details td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #334155;
            }}
            .order-details th {{
                color: #94a3b8;
                font-weight: 600;
                width: 35%;
            }}
            .button-container {{
                text-align: center;
                margin: 30px 0;
            }}
            .button {{
                background-color: #38bdf8;
                color: #0f172a;
                padding: 15px 30px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                display: inline-block;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #64748b;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>New Order Received</h1>
            </div>
            <div class="content">
                <table class="order-details">
                    <tr>
                        <th>Order ID</th>
                        <td>{order_id}</td>
                    </tr>
                    <tr>
                        <th>Username</th>
                        <td>{username}</td>
                    </tr>
                    <tr>
                        <th>User Email</th>
                        <td>{user_email}</td>
                    </tr>
                    <tr>
                        <th>Product</th>
                        <td>{product_name} ({region})</td>
                    </tr>
                    <tr>
                        <th>User ID</th>
                        <td>{userid}</td>
                    </tr>
                    <tr>
                        <th>Zone ID</th>
                        <td>{zoneid or '-'}</td>
                    </tr>
                    <tr>
                        <th>Amount</th>
                        <td>₹{amount}</td>
                    </tr>
                    <tr>
                        <th>Payment Type</th>
                        <td>{payment_type}</td>
                    </tr>
                    <tr>
                        <th>Timestamp</th>
                        <td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
                    </tr>
                </table>
                
                <div class="button-container">
                    <a href="{SITE_URL}/admin/orders" class="button">View in Admin Panel</a>
                </div>
            </div>
            <div class="footer">
                This is an automated notification from Kendy Enterprises.
            </div>
        </div>
    </body>
    </html>
    """

def send_order_email_to_user(email, username, order_id, product_name, userid, zoneid, amount, payment_type, region):
    """Send order confirmation email to user"""
    html_content = get_user_order_template(
        username=username,
        order_id=order_id,
        product_name=product_name,
        userid=userid,
        zoneid=zoneid,
        amount=amount,
        payment_type=payment_type,
        region=region
    )
    send_email_with_template(
        to_email=email,
        subject='Order Confirmation - Kendy Enterprises',
        html_content=html_content
    )

def send_order_email_to_admin(order_id, username, user_email, product_name, userid, zoneid, amount, payment_type, region):
    """Send order notification email to admin"""
    html_content = get_admin_order_template(
        order_id=order_id,
        username=username,
        user_email=user_email,
        product_name=product_name,
        userid=userid,
        zoneid=zoneid,
        amount=amount,
        payment_type=payment_type,
        region=region
    )
    send_email_with_template(
        to_email=ADMIN_EMAIL,
        subject=f'New Order #{order_id} - Kendy Enterprises',
        html_content=html_content
    )