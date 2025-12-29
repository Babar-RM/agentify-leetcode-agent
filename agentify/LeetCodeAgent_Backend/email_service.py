"""
Email Service using Brevo SDK (sib_api_v3_sdk)
Handles welcome emails and daily problem emails
"""

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from typing import Dict
from datetime import datetime

class BrevoEmailService:
    def __init__(self, api_key: str, sender_email: str = 'kingarain7866@gmail.com', sender_name: str = 'LeetCode Daily Challenge'):
        """
        Initialize Brevo email service with SDK
        
        Args:
            api_key: Brevo API key
            sender_email: Verified sender email (default: kingarain7866@gmail.com)
            sender_name: Sender name
        """
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name
        
        # Configure SDK
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
    
    def send_welcome_email(self, user_email: str, username: str, total_problems: int) -> bool:
        """Send welcome email after user registration"""
        subject = "🎉 Welcome to LeetCode Daily Challenge!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 30px; text-align: center; border-radius: 10px; }}
                .content {{ background: #f9f9f9; padding: 30px; margin: 20px 0; border-radius: 10px; }}
                .stats {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; 
                         border-left: 4px solid #667eea; }}
                .button {{ background: #667eea; color: white; padding: 15px 30px; 
                          text-decoration: none; border-radius: 5px; display: inline-block; 
                          margin: 20px 0; }}
                .footer {{ text-align: center; color: #666; margin-top: 30px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Welcome to LeetCode Daily Challenge!</h1>
                    <p>Your personalized coding journey starts now</p>
                </div>
                
                <div class="content">
                    <h2>Hi {username}! 👋</h2>
                    
                    <p>Thank you for joining LeetCode Daily Challenge! We've successfully analyzed your GitHub repository and you're all set.</p>
                    
                    <div class="stats">
                        <h3>📊 Your Profile Summary:</h3>
                        <ul>
                            <li><strong>Total problems analyzed:</strong> {total_problems}</li>
                            <li><strong>GitHub repository:</strong> Successfully connected</li>
                            <li><strong>Email notifications:</strong> Enabled ✅</li>
                        </ul>
                    </div>
                    
                    <h3>🎯 What happens next?</h3>
                    <ul>
                        <li><strong>Tomorrow at 8:00 AM:</strong> You'll receive your first personalized LeetCode problem</li>
                        <li><strong>Daily emails:</strong> Each problem is carefully selected based on your solving patterns</li>
                        <li><strong>Smart recommendations:</strong> AI analyzes your strengths and suggests the perfect next challenge</li>
                    </ul>
                    
                    <p style="margin-top: 30px;">
                        <a href="https://leetcode.com" class="button">Visit LeetCode</a>
                    </p>
                </div>
                
                <div class="footer">
                    <p>You're receiving this email because you registered for LeetCode Daily Challenge</p>
                    <p>© 2024 LeetCode Daily Challenge. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Hi {username}!

Thank you for joining LeetCode Daily Challenge!

Your Profile Summary:
- Total problems analyzed: {total_problems}
- GitHub repository: Successfully connected
- Email notifications: Enabled

What happens next?
- Tomorrow at 8:00 AM: You'll receive your first personalized LeetCode problem
- Daily emails: Each problem is carefully selected based on your solving patterns
- Smart recommendations: AI analyzes your strengths and suggests the perfect next challenge

Visit LeetCode: https://leetcode.com

You're receiving this email because you registered for LeetCode Daily Challenge.
© 2024 LeetCode Daily Challenge. All rights reserved.
        """
        
        return self._send_email(user_email, username, subject, html_content, text_content)
    
    def send_daily_problem_email(self, user_email: str, username: str, problem: Dict) -> bool:
        """Send daily problem recommendation email"""
        subject = f"🎯 Today's Challenge: {problem.get('problem_title')}"
        
        difficulty = problem.get('difficulty', 'Medium')
        difficulty_colors = {
            'Easy': '#00b8a3',
            'Medium': '#ffc01e',
            'Hard': '#ef4743'
        }
        difficulty_color = difficulty_colors.get(difficulty, '#ffc01e')
        
        concepts = problem.get('key_concepts', [])
        concepts_html = ''.join([f'<li>{concept}</li>' for concept in concepts])
        concepts_text = '\n'.join([f'  • {concept}' for concept in concepts])
        
        hints = problem.get('hints', [])
        hints_html = ''.join([f'<li>{hint}</li>' for hint in hints])
        hints_text = '\n'.join([f'  {i}. {hint}' for i, hint in enumerate(hints, 1)])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 30px; text-align: center; border-radius: 10px; }}
                .problem-card {{ background: white; padding: 30px; margin: 20px 0; 
                                border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .difficulty {{ display: inline-block; padding: 5px 15px; border-radius: 20px; 
                              color: white; font-weight: bold; background: {difficulty_color}; }}
                .section {{ margin: 20px 0; }}
                .button {{ background: #667eea; color: white; padding: 15px 30px; 
                          text-decoration: none; border-radius: 5px; display: inline-block; 
                          margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; color: #666; margin-top: 30px; font-size: 12px; }}
                ul {{ padding-left: 20px; }}
                li {{ margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 Your Daily LeetCode Challenge</h1>
                    <p>{datetime.now().strftime('%B %d, %Y')}</p>
                </div>
                
                <div class="problem-card">
                    <h2>Hi {username}! 👋</h2>
                    <p>Based on your solving patterns, here's your personalized problem for today:</p>
                    
                    <div class="section">
                        <h2>📝 Problem #{problem.get('problem_number')}: {problem.get('problem_title')}</h2>
                        <span class="difficulty">{difficulty}</span>
                    </div>
                    
                    <div class="section">
                        <h3>💡 Why this problem?</h3>
                        <p>{problem.get('why_recommended', 'Perfect for your current skill level')}</p>
                    </div>
                    
                    <div class="section">
                        <h3>🔑 Key Concepts:</h3>
                        <ul>
                            {concepts_html}
                        </ul>
                    </div>
                    
                    <div class="section">
                        <h3>⏱️ Estimated Time: {problem.get('estimated_time', '30 minutes')}</h3>
                    </div>
                    
                    {f'''
                    <div class="section">
                        <h3>💭 Hints to get started:</h3>
                        <ul>
                            {hints_html}
                        </ul>
                    </div>
                    ''' if hints else ''}
                    
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{problem.get('leetcode_url', 'https://leetcode.com')}" class="button">
                            Start Solving Now! 🚀
                        </a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>Keep up the great work! 💪</p>
                    <p>Tomorrow's challenge will be even better!</p>
                    <p style="margin-top: 20px;">
                        <small>You're receiving this because you subscribed to LeetCode Daily Challenge</small>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
🎯 Your Daily LeetCode Challenge
{datetime.now().strftime('%B %d, %Y')}

Hi {username}!

Based on your solving patterns, here's your personalized problem for today:

📝 Problem #{problem.get('problem_number')}: {problem.get('problem_title')}
🎚️ Difficulty: {difficulty}

💡 Why this problem?
{problem.get('why_recommended', 'Perfect for your current skill level')}

🔑 Key Concepts:
{concepts_text}

⏱️ Estimated Time: {problem.get('estimated_time', '30 minutes')}

{f'''💭 Hints to get started:
{hints_text}
''' if hints else ''}

🚀 Start solving: {problem.get('leetcode_url', 'https://leetcode.com')}

Keep up the great work! 💪
Tomorrow's challenge will be even better!

You're receiving this because you subscribed to LeetCode Daily Challenge.
        """
        
        return self._send_email(user_email, username, subject, html_content, text_content)
    
    def _send_email(self, to_email: str, to_name: str, subject: str, html_content: str, text_content: str) -> bool:
        """
        Internal method to send email via Brevo SDK
        
        Args:
            to_email: Recipient email
            to_name: Recipient name
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text email content
            
        Returns:
            True if successful
        """
        try:
            # Create sender
            sender = sib_api_v3_sdk.SendSmtpEmailSender(
                name=self.sender_name,
                email=self.sender_email
            )
            
            # Create recipient
            to = [sib_api_v3_sdk.SendSmtpEmailTo(
                email=to_email,
                name=to_name
            )]
            
            # Create email
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                sender=sender,
                to=to,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            # Send email
            api_response = self.api_instance.send_transac_email(send_smtp_email)
            
            print(f"✅ Email sent successfully to {to_email}")
            print(f"   Message ID: {api_response.message_id}")
            return True
            
        except ApiException as e:
            print(f"❌ Failed to send email to {to_email}")
            print(f"   Error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending email: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Brevo API connection"""
        try:
            # Try to get account info
            account_api = sib_api_v3_sdk.AccountApi(
                sib_api_v3_sdk.ApiClient(
                    sib_api_v3_sdk.Configuration(api_key={'api-key': self.api_key})
                )
            )
            account = account_api.get_account()
            
            print(f"✅ Brevo API connected successfully")
            print(f"   Account email: {account.email}")
            print(f"   Plan: {account.plan[0].type if account.plan else 'N/A'}")
            return True
        except ApiException as e:
            print(f"❌ Brevo API connection failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Brevo API test error: {e}")
            return False