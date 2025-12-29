"""
Daily Scheduler - Sends personalized LeetCode problems every day at 8 AM
"""

import schedule
import time
import json
import psycopg2
import requests
from datetime import datetime, date
from typing import List, Dict
from email_service import BrevoEmailService

class DailyProblemScheduler:
    def __init__(self, config_file='config.json'):
        """Initialize scheduler with configuration"""
        self.load_config(config_file)
        
        # FIX: Initialize email service with nested config access
        self.email_service = BrevoEmailService(
            self.brevo_api_key, 
            sender_email=self.brevo_sender_email, 
            sender_name=self.brevo_sender_name
        )
        
    def load_config(self, config_file):
        """Load configuration from file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            self.gemini_api_key = config['gemini_api_key']
            
            # FIX: Reconstruct the DB URL from the nested 'database' structure
            self.neon_db_url = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}:{config['database']['port']}/{config['database']['dbname']}?sslmode={config['database']['sslmode']}"
            
            # FIX: Access email details from the nested 'email' structure
            self.brevo_api_key = config['email']['api_key']
            self.brevo_sender_email = config['email']['sender_email']
            self.brevo_sender_name = config['email']['sender_name']
            
            print("✅ Configuration loaded")
        except Exception as e:
            # Reraise the exception for main.py to catch and log
            raise Exception(f"Error loading config in DailyProblemScheduler: {e}")
    
    # ... (rest of the file remains the same, assuming logic is fine) ...

    def get_active_users(self) -> List[Dict]:
        """Get all active users from database"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT email, github_username, github_repo_url, last_problem_sent_date
                FROM users
                WHERE is_active = TRUE
            """)
            
            users = []
            for row in cursor.fetchall():
                users.append({
                    'email': row[0],
                    'github_username': row[1],
                    'github_repo_url': row[2],
                    'last_problem_sent_date': row[3]
                })
            
            cursor.close()
            conn.close()
            
            return users
        except Exception as e:
            print(f"❌ Error fetching users: {e}")
            return []
    
    def get_user_solved_problems(self, user_email: str) -> List[Dict]:
        """Get all problems solved by user from database"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT problem_number, problem_title, difficulty, 
                       algorithms, data_structures, tags
                FROM leetcode_solutions
                WHERE user_email = %s
            """, (user_email,))
            
            problems = []
            for row in cursor.fetchall():
                problems.append({
                    'problem_number': row[0],
                    'problem_title': row[1],
                    'difficulty': row[2],
                    'algorithms': row[3] or [],
                    'data_structures': row[4] or [],
                    'tags': row[5] or []
                })
            
            cursor.close()
            conn.close()
            
            return problems
        except Exception as e:
            print(f"❌ Error fetching user problems: {e}")
            return []
    
    def get_sent_problems(self, user_email: str) -> List[str]:
        """Get list of problem numbers already sent to user"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT problem_number
                FROM daily_sent_problems
                WHERE user_email = %s
            """, (user_email,))
            
            sent_problems = [row[0] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            return sent_problems
        except Exception as e:
            print(f"❌ Error fetching sent problems: {e}")
            return []
    
    def generate_problem_with_gemini(self, user_email: str, solved_problems: List[Dict], sent_problems: List[str]) -> Dict:
        """Generate new problem recommendation using Gemini"""
        
        difficulties = [p.get('difficulty', 'Unknown') for p in solved_problems]
        algorithms = []
        data_structures = []
        tags = []
        
        for prob in solved_problems:
            algorithms.extend(prob.get('algorithms', []))
            data_structures.extend(prob.get('data_structures', []))
            tags.extend(prob.get('tags', []))
        
        summary = {
            'total_solved': len(solved_problems),
            'easy_count': difficulties.count('Easy'),
            'medium_count': difficulties.count('Medium'),
            'hard_count': difficulties.count('Hard'),
            'most_used_algorithms': list(set(algorithms))[:10],
            'most_used_data_structures': list(set(data_structures))[:10],
            'topics_covered': list(set(tags))[:15]
        }
        
        prompt = f"""Based on this user's LeetCode profile, recommend ONE new problem they haven't solved yet.

User's Profile:
- Total problems solved: {summary['total_solved']}
- Easy: {summary['easy_count']}, Medium: {summary['medium_count']}, Hard: {summary['hard_count']}
- Algorithms used: {', '.join(summary['most_used_algorithms']) if summary['most_used_algorithms'] else 'Various'}
- Data structures used: {', '.join(summary['most_used_data_structures']) if summary['most_used_data_structures'] else 'Various'}
- Topics covered: {', '.join(summary['topics_covered']) if summary['topics_covered'] else 'Various'}

Already sent problems (DO NOT recommend these): {', '.join(sent_problems[:50]) if sent_problems else 'None'}

Recommend a NEW problem that:
1. They haven't been recommended before
2. Matches their skill progression
3. Introduces new concepts or reinforces weak areas
4. Is from LeetCode's actual problem set

Return ONLY JSON (no markdown):
{{
  "problem_number": "number",
  "problem_title": "exact title from LeetCode",
  "difficulty": "Easy/Medium/Hard",
  "leetcode_url": "https://leetcode.com/problems/problem-name/",
  "why_recommended": "brief explanation (max 150 chars)",
  "key_concepts": ["concept1", "concept2"],
  "estimated_time": "time estimate",
  "hints": ["hint1", "hint2"]
}}"""
        
        try:
            response = self.call_gemini_api(prompt)
            recommendation = self.parse_recommendation_response(response)
            return recommendation
        except Exception as e:
            print(f"❌ Error generating recommendation: {e}")
            return {
                'problem_number': '1',
                'problem_title': 'Two Sum',
                'difficulty': 'Easy',
                'leetcode_url': 'https://leetcode.com/problems/two-sum/',
                'why_recommended': 'Classic hash table problem',
                'key_concepts': ['Hash Table', 'Array'],
                'estimated_time': '15-20 minutes',
                'hints': ['Use hash map', 'Single pass solution']
            }
    
    def call_gemini_api(self, prompt: str) -> str:
        """Call Gemini API"""
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 8192,
            }
        }
        
        response = requests.post(
            f"{url}?key={self.gemini_api_key}",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            raise Exception(f"Gemini API Error: {response.status_code}")
    
    def parse_recommendation_response(self, response: str) -> Dict:
        """Parse Gemini's JSON response"""
        response = response.replace('```json', '').replace('```', '').strip()
        start = response.find('{')
        end = response.rfind('}') + 1
        
        if start != -1 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        else:
            raise ValueError("No JSON found")
    
    def save_sent_problem(self, user_email: str, problem: Dict):
        """Save sent problem to database"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO daily_sent_problems 
                (user_email, problem_number, problem_title, difficulty, leetcode_url)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                user_email,
                problem.get('problem_number'),
                problem.get('problem_title'),
                problem.get('difficulty'),
                problem.get('leetcode_url')
            ))
            
            cursor.execute("""
                UPDATE users
                SET last_problem_sent_date = CURRENT_DATE
                WHERE email = %s
            """, (user_email,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Saved sent problem for {user_email}")
        except Exception as e:
            print(f"❌ Error saving sent problem: {e}")
    
    def send_daily_problems(self):
        """Main function to send daily problems to all active users"""
        print("\n" + "=" * 70)
        print(f"🚀 DAILY PROBLEM SENDER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Initialize email service with sender details
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            sender_email = config['email']['sender_email']
            sender_name = config['email']['sender_name']
            
            from email_service import BrevoEmailService
            email_service = BrevoEmailService(
                config['email']['api_key'],
                sender_email=sender_email,
                sender_name=sender_name
            )
        except Exception as e:
            print(f"❌ Failed to initialize email service: {e}")
            return
        
        users = self.get_active_users()
        
        if not users:
            print("⚠️ No active users found")
            return
        
        print(f"📧 Processing {len(users)} users...")
        
        success_count = 0
        error_count = 0
        
        for user in users:
            email = user['email']
            username = user['github_username']
            last_sent = user['last_problem_sent_date']
            
            if last_sent == date.today():
                print(f"⏭️  Skipping {email} (already sent today)")
                continue
            
            print(f"\n📧 Processing: {email}")
            
            try:
                solved_problems = self.get_user_solved_problems(email)
                print(f"   Found {len(solved_problems)} solved problems")
                
                sent_problems = self.get_sent_problems(email)
                print(f"   Previously sent: {len(sent_problems)} problems")
                
                print(f"   🤖 Generating recommendation with Gemini...")
                problem = self.generate_problem_with_gemini(email, solved_problems, sent_problems)
                print(f"   ✅ Recommended: {problem.get('problem_title')}")
                
                print(f"   📧 Sending email...")
                success = email_service.send_daily_problem_email(email, username, problem)
                
                if success:
                    self.save_sent_problem(email, problem)
                    success_count += 1
                else:
                    error_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error: {e}")
        
        print("\n" + "=" * 70)
        print(f"✅ COMPLETED")
        print(f"   • Success: {success_count} emails sent")
        print(f"   • Errors: {error_count}")
        print("=" * 70)
    
    def start_scheduler(self):
        """Start the daily scheduler"""
        print("\n" + "=" * 70)
        print("🤖 LEETCODE DAILY PROBLEM SCHEDULER")
        print("=" * 70)
        print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Scheduled time: Every day at 08:00 AM")
        print("\n✅ Scheduler started. Press Ctrl+C to stop.")
        print("=" * 70)
        
        schedule.every().day.at("14:35").do(self.send_daily_problems)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n\n👋 Scheduler stopped by user")

def main():
    """Main function"""
    scheduler = DailyProblemScheduler()
    
    # Uncomment to test immediately:
    # scheduler.send_daily_problems()
    
    # Start scheduler (runs at 8 AM daily)
    scheduler.start_scheduler()

if __name__ == "__main__":
    main()