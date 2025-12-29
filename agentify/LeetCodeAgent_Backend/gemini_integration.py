import os
import json
import requests
import re
from typing import List, Dict, Any
import time
import psycopg2
from psycopg2.extras import Json
from leetcode_analyzer import LeetCodeRepoAnalyzer # Assuming this utility exists

class AutomatedLeetCodeSystem:
    def __init__(self, gemini_api_key: str, neon_db_url: str, github_token: str = None, brevo_api_key: str = None, brevo_sender_email: str = None, brevo_sender_name: str = None):
        """
        Fully automated system: GitHub -> Gemini -> PostgreSQL -> Email
        """
        self.gemini_api_key = gemini_api_key
        
        # Fix Neon URL
        if 'postgresql+asyncpg://' in neon_db_url:
            neon_db_url = neon_db_url.replace('postgresql+asyncpg://', 'postgresql://')
        if neon_db_url.count('postgresql://') > 1:
            neon_db_url = 'postgresql://' + neon_db_url.split('postgresql://')[-1]
        
        self.neon_db_url = neon_db_url
        self.github_token = github_token
        self.brevo_api_key = brevo_api_key
        self.brevo_sender_email = brevo_sender_email or 'kingarain7866@gmail.com'
        self.brevo_sender_name = brevo_sender_name or 'Agentify'
        
        self.analyzer = LeetCodeRepoAnalyzer(github_token) # Re-use the analyzer logic
        
        self.headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            self.headers['Authorization'] = f'token {github_token}'
    
    def parse_github_url(self, url: str) -> tuple:
        """Parse GitHub URL to extract owner, repo, and optional path"""
        url = url.rstrip('/')
        
        # Handle tree URLs
        tree_pattern = r'github\.com/([^/]+)/([^/]+)/tree/[^/]+/(.+)'
        match = re.search(tree_pattern, url)
        if match:
            return match.group(1), match.group(2).replace('.git', ''), match.group(3)
        
        # Handle regular URLs
        pattern = r'github\.com/([^/]+)/([^/]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2).replace('.git', ''), ""
        
        raise ValueError("Invalid GitHub URL format")
    
    def test_connection(self):
        """Test internet and GitHub API connection"""
        print("🔍 Testing connections...")
        
        try:
            requests.get('https://www.google.com', timeout=5)
            print("✅ Internet connection OK")
        except Exception as e:
            print(f"❌ No internet connection: {e}")
            raise
        
        try:
            response = requests.get('https://api.github.com', headers=self.headers, timeout=5)
            print("✅ GitHub API connection OK")
        except Exception as e:
            print(f"❌ Cannot reach GitHub API: {e}")
            raise
    
    def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """Get repository contents from GitHub"""
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"⚠️ Path not found: {path}")
                return []
            elif response.status_code == 403:
                print(f"⚠️ Rate limit exceeded. Please add GitHub token to config.json")
                return []
            else:
                print(f"⚠️ GitHub API error {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return []
    
    def is_code_file(self, filename: str) -> bool:
        """Check if file is a code file"""
        extensions = ['.py', '.java', '.cpp', '.c', '.js', '.ts', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.cs']
        return any(filename.endswith(ext) for ext in extensions)
    
    def get_file_content(self, download_url: str) -> str:
        """Download file content"""
        try:
            response = requests.get(download_url, timeout=10)
            return response.text if response.status_code == 200 else ""
        except Exception as e:
            print(f"⚠️ Error downloading file: {e}")
            return ""
    
    def extract_problem_number(self, filename: str, path: str) -> str:
        """Extract problem number from filename or path"""
        match = re.search(r'(\d{1,4})', filename)
        if match:
            return match.group(1)
        match = re.search(r'problem[_-]?(\d{4})', path)
        if match:
            return match.group(1)
        return "Unknown"
    
    def get_language(self, filename: str) -> str:
        """Get programming language from extension"""
        ext_map = {
            '.py': 'Python', '.java': 'Java', '.cpp': 'C++', '.c': 'C',
            '.js': 'JavaScript', '.ts': 'TypeScript', '.go': 'Go',
            '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP', '.swift': 'Swift',
            '.kt': 'Kotlin', '.cs': 'C#'
        }
        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang
        return "Unknown"
    
    def scan_repository(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """Recursively scan repository for code files"""
        problems = []
        contents = self.get_repo_contents(owner, repo, path)
        
        if not contents:
            return []
        
        for item in contents:
            if item['type'] == 'file' and self.is_code_file(item['name']):
                if 'test' in item['path'].lower() or 'helper' in item['path'].lower():
                    continue
                
                print(f"✓ Found: {item['path']}")
                code = self.get_file_content(item['download_url'])
                if code:
                    problems.append({
                        'filename': item['name'],
                        'path': item['path'],
                        'code': code,
                        'language': self.get_language(item['name']),
                        'problem_number': self.extract_problem_number(item['name'], item['path'])
                    })
            elif item['type'] == 'dir':
                problems.extend(self.scan_repository(owner, repo, item['path']))
        
        return problems
    
    def call_gemini_api(self, prompt: str) -> str:
        """Call Gemini API with prompt"""
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
        
        try:
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
                raise Exception(f"Gemini API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            raise
    
    def analyze_with_gemini(self, problems: List[Dict]) -> List[Dict]:
        """Analyze problems with Gemini in batches"""
        all_analyzed = []
        batch_size = 3
        
        total_batches = (len(problems) - 1) // batch_size + 1
        
        for i in range(0, len(problems), batch_size):
            batch = problems[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"\n🤖 Analyzing batch {batch_num}/{total_batches} ({len(batch)} solutions)...")
            
            prompt = self.create_gemini_prompt(batch)
            
            try:
                response = self.call_gemini_api(prompt)
                analyzed = self.parse_gemini_response(response, batch)
                
                if analyzed:
                    all_analyzed.extend(analyzed)
                    print(f"✅ Successfully analyzed {len(analyzed)} solutions")
                else:
                    print(f"⚠️ Failed to parse Gemini response, adding basic info")
                    for p in batch:
                        all_analyzed.append({
                            'problem_number': p['problem_number'],
                            'problem_title': p['filename'].replace(p['language'].lower(), '').replace('.', ' ').strip(),
                            'difficulty': 'Unknown',
                            'language': p['language'],
                            'time_complexity': 'Unknown',
                            'space_complexity': 'Unknown',
                            'algorithms': [],
                            'data_structures': [],
                            'explanation': 'Analysis pending',
                            'tags': [],
                            'code': p['code'],
                            'path': p['path']
                        })
            except Exception as e:
                print(f"❌ Error in batch {batch_num}: {str(e)}")
                for p in batch:
                    all_analyzed.append({
                        'problem_number': p['problem_number'],
                        'problem_title': p['filename'],
                        'difficulty': 'Unknown',
                        'language': p['language'],
                        'time_complexity': 'Unknown',
                        'space_complexity': 'Unknown',
                        'algorithms': [],
                        'data_structures': [],
                        'explanation': 'Analysis failed',
                        'tags': [],
                        'code': p['code'],
                        'path': p['path']
                    })
            
            if i + batch_size < len(problems):
                print("⏳ Waiting 2 seconds (rate limiting)...")
                time.sleep(2)
        
        return all_analyzed
    
    def create_gemini_prompt(self, problems: List[Dict]) -> str:
        """Create prompt for Gemini"""
        prompt = """Analyze these LeetCode solutions and return ONLY a valid JSON array with no markdown formatting.

For each solution, provide this structure:
{
  "problem_number": "extract the number",
  "problem_title": "proper LeetCode problem title",
  "difficulty": "Easy/Medium/Hard",
  "time_complexity": "O(n) format",
  "space_complexity": "O(n) format",
  "algorithms": ["algorithm1", "algorithm2"],
  "data_structures": ["structure1"],
  "explanation": "brief explanation under 150 chars",
  "tags": ["tag1", "tag2"]
}

Return format: [{"problem_number":"1",...},{"problem_number":"2",...}]
No backticks, no markdown, just pure JSON array.

Solutions to analyze:
"""
        
        for i, p in enumerate(problems, 1):
            prompt += f"\n--- Solution {i} ---\n"
            prompt += f"File: {p['filename']}\n"
            prompt += f"Language: {p['language']}\n"
            prompt += f"Code:\n{p['code'][:1200]}\n"
        
        return prompt
    
    def parse_gemini_response(self, response: str, original_problems: List[Dict]) -> List[Dict]:
        """Parse Gemini JSON response"""
        try:
            response = response.replace('```json', '').replace('```', '').strip()
            
            start = response.find('[')
            end = response.rfind(']') + 1
            
            if start == -1 or end == 0:
                print("⚠️ No JSON array found in response")
                return []
            
            json_str = response[start:end]
            analyzed = json.loads(json_str)
            
            for i, analysis in enumerate(analyzed):
                if i < len(original_problems):
                    analysis['code'] = original_problems[i]['code']
                    analysis['path'] = original_problems[i]['path']
                    if 'language' not in analysis:
                        analysis['language'] = original_problems[i]['language']
            
            return analyzed
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {str(e)}")
            return []
        except Exception as e:
            print(f"⚠️ Parse error: {str(e)}")
            return []
    
    def setup_database(self):
        """Create database tables if not exist"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leetcode_solutions (
                    id SERIAL PRIMARY KEY,
                    problem_number VARCHAR(10),
                    problem_title VARCHAR(255),
                    difficulty VARCHAR(20),
                    language VARCHAR(50),
                    time_complexity VARCHAR(50),
                    space_complexity VARCHAR(50),
                    algorithms TEXT[],
                    data_structures TEXT[],
                    explanation TEXT,
                    tags TEXT[],
                    code TEXT,
                    file_path VARCHAR(500),
                    user_email VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(problem_number, language, file_path, user_email)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS problem_recommendations (
                    id SERIAL PRIMARY KEY,
                    problem_number VARCHAR(10),
                    problem_title VARCHAR(255),
                    difficulty VARCHAR(20),
                    leetcode_url VARCHAR(500),
                    why_recommended TEXT,
                    key_concepts TEXT[],
                    estimated_time VARCHAR(50),
                    hints TEXT[],
                    user_email VARCHAR(255),
                    recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'pending',
                    sent_via_email BOOLEAN DEFAULT FALSE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    github_username VARCHAR(255),
                    github_repo_url TEXT,
                    total_problems_analyzed INTEGER DEFAULT 0,
                    last_problem_sent_date DATE,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_sent_problems (
                    id SERIAL PRIMARY KEY,
                    user_email VARCHAR(255),
                    problem_number VARCHAR(10),
                    problem_title VARCHAR(255),
                    difficulty VARCHAR(20),
                    leetcode_url VARCHAR(500),
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    opened BOOLEAN DEFAULT FALSE
                )
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Database tables ready")
        except Exception as e:
            print(f"❌ Database setup error: {e}")
            raise
    
    def store_in_database(self, solutions: List[Dict], user_email: str = None):
        """Store solutions in PostgreSQL"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            inserted = 0
            updated = 0
            
            for sol in solutions:
                try:
                    cursor.execute("""
                        INSERT INTO leetcode_solutions 
                        (problem_number, problem_title, difficulty, language,
                         time_complexity, space_complexity, algorithms, 
                         data_structures, explanation, tags, code, file_path, user_email)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (problem_number, language, file_path, user_email) DO UPDATE
                        SET problem_title = EXCLUDED.problem_title,
                            difficulty = EXCLUDED.difficulty,
                            time_complexity = EXCLUDED.time_complexity,
                            space_complexity = EXCLUDED.space_complexity,
                            algorithms = EXCLUDED.algorithms,
                            data_structures = EXCLUDED.data_structures,
                            explanation = EXCLUDED.explanation,
                            tags = EXCLUDED.tags,
                            code = EXCLUDED.code
                        RETURNING (xmax = 0) AS inserted
                    """, (
                        sol.get('problem_number', 'Unknown'),
                        sol.get('problem_title', 'Unknown'),
                        sol.get('difficulty', 'Unknown'),
                        sol.get('language', 'Unknown'),
                        sol.get('time_complexity', 'Unknown'),
                        sol.get('space_complexity', 'Unknown'),
                        sol.get('algorithms', []),
                        sol.get('data_structures', []),
                        sol.get('explanation', ''),
                        sol.get('tags', []),
                        sol.get('code', ''),
                        sol.get('path', ''),
                        user_email
                    ))
                    
                    was_inserted = cursor.fetchone()[0]
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1
                        
                except Exception as e:
                    print(f"⚠️ Skipped one solution: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"\n✅ Database operation complete:")
            print(f"   • Inserted: {inserted} new solutions")
            print(f"   • Updated: {updated} existing solutions")
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            raise
    
    def register_user(self, email: str, github_username: str, github_repo_url: str, total_problems: int):
        """Register or update user in database"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (email, github_username, github_repo_url, total_problems_analyzed)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE
                SET github_username = EXCLUDED.github_username,
                    github_repo_url = EXCLUDED.github_repo_url,
                    total_problems_analyzed = users.total_problems_analyzed + EXCLUDED.total_problems_analyzed
            """, (email, github_username, github_repo_url, total_problems))
            
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✅ User registered: {email}")
            return True
        except Exception as e:
            print(f"❌ User registration error: {e}")
            return False
    
    def process_repository(self, github_url: str, user_email: str = None):
        """Main automated process"""
        print("=" * 70)
        print("🚀 AUTOMATED LEETCODE ANALYZER")
        print("=" * 70)
        
        try:
            self.test_connection()
        except Exception:
            print("\n❌ Connection test failed. Please fix the issues above and try again.")
            return
        
        print("\n" + "=" * 70)
        print("[1/5] 📥 EXTRACTING FROM GITHUB")
        print("=" * 70)
        
        try:
            owner, repo, start_path = self.parse_github_url(github_url)
            print(f"Repository: {owner}/{repo}")
            if start_path:
                print(f"Starting path: {start_path}")
            
            problems = self.scan_repository(owner, repo, start_path)
            
            if not problems:
                print("\n❌ No solutions found!")
                return
            
            print(f"\n✅ Found {len(problems)} code files")
            
        except Exception as e:
            print(f"\n❌ GitHub extraction error: {e}")
            return
        
        print("\n" + "=" * 70)
        print("[2/5] 🤖 ANALYZING WITH GEMINI AI")
        print("=" * 70)
        
        try:
            analyzed = self.analyze_with_gemini(problems)
            print(f"\n✅ Analyzed {len(analyzed)} solutions total")
        except Exception as e:
            print(f"\n❌ Gemini analysis error: {e}")
            return
        
        print("\n" + "=" * 70)
        print("[3/5] 🗄️ SETTING UP DATABASE")
        print("=" * 70)
        
        try:
            self.setup_database()
        except Exception as e:
            print(f"\n❌ Database setup error: {e}")
            return
        
        print("\n" + "=" * 70)
        print("[4/5] 💾 STORING IN POSTGRESQL")
        print("=" * 70)
        
        try:
            self.store_in_database(analyzed, user_email)
        except Exception as e:
            print(f"\n❌ Database storage error: {e}")
            return
        
        print("\n" + "=" * 70)
        print("[5/5] 📧 USER REGISTRATION & WELCOME EMAIL")
        print("=" * 70)
        
        if user_email and self.brevo_api_key:
            self.register_user(user_email, owner, github_url, len(analyzed))
            
            try:
                from email_service import BrevoEmailService
                
                # Get sender details from config if available
                sender_email = getattr(self, 'brevo_sender_email', 'kingarain7866@gmail.com')
                sender_name = getattr(self, 'brevo_sender_name', 'Agentify')
                
                email_service = BrevoEmailService(
                    self.brevo_api_key,
                    sender_email=sender_email,
                    sender_name=sender_name
                )
                email_service.send_welcome_email(user_email, owner, len(analyzed))
                print(f"✅ Welcome email sent to {user_email}")
            except Exception as e:
                print(f"⚠️ Could not send welcome email: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️ Email service not configured or email not provided")
        
        print("\n" + "=" * 70)
        print("✅ PROCESS COMPLETE!")
        print("=" * 70)
        print(f"📊 Summary:")
        print(f"   • Total solutions processed: {len(analyzed)}")
        print(f"   • Languages: {set(s.get('language', 'Unknown') for s in analyzed)}")
        if user_email:
            print(f"   • Email: {user_email}")
            print(f"   • Daily emails: Will start tomorrow at 8:00 AM")
        
        print("\n" + "=" * 70)
        print("🎯 GENERATING PERSONALIZED RECOMMENDATION")
        print("=" * 70)
        
        try:
            recommendation = self.get_personalized_recommendation(analyzed, user_email)
            self.display_recommendation(recommendation)
            
            save_choice = input("\n💾 Save this recommendation to database? (y/n): ").strip().lower()
            if save_choice in ['y', 'yes']:
                self.save_recommendation(recommendation, user_email)
        except Exception as e:
            print(f"⚠️ Could not generate recommendation: {e}")
        
        print("\n💡 Next steps:")
        print("   • Check your Neon dashboard: https://console.neon.tech")
        if user_email:
            print(f"   • Check your email ({user_email}) for welcome message")
            print(f"   • Tomorrow at 8 AM: You'll receive your first daily problem!")
        print("=" * 70)
    
    def get_personalized_recommendation(self, analyzed_solutions: List[Dict], user_email: str = None) -> Dict:
        """Get personalized recommendation"""
        print("🤖 Analyzing your problem-solving patterns...")
        
        difficulties = [s.get('difficulty', 'Unknown') for s in analyzed_solutions]
        algorithms = []
        data_structures = []
        tags = []
        
        for sol in analyzed_solutions:
            algorithms.extend(sol.get('algorithms', []))
            data_structures.extend(sol.get('data_structures', []))
            tags.extend(sol.get('tags', []))
        
        summary = {
            'total_solved': len(analyzed_solutions),
            'easy_count': difficulties.count('Easy'),
            'medium_count': difficulties.count('Medium'),
            'hard_count': difficulties.count('Hard'),
            'most_used_algorithms': list(set(algorithms))[:10],
            'most_used_data_structures': list(set(data_structures))[:10],
            'topics_covered': list(set(tags))[:15]
        }
        
        prompt = f"""Based on this LeetCode solving profile, recommend ONE new problem.

User's Profile:
- Total solved: {summary['total_solved']}
- Easy: {summary['easy_count']}, Medium: {summary['medium_count']}, Hard: {summary['hard_count']}
- Algorithms: {', '.join(summary['most_used_algorithms']) if summary['most_used_algorithms'] else 'Various'}
- Data structures: {', '.join(summary['most_used_data_structures']) if summary['most_used_data_structures'] else 'Various'}
- Topics: {', '.join(summary['topics_covered']) if summary['topics_covered'] else 'Various'}

Return ONLY JSON (no markdown):
{{
  "problem_number": "number",
  "problem_title": "title from LeetCode",
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
            print(f"⚠️ Error: {e}")
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
    
    def parse_recommendation_response(self, response: str) -> Dict:
        """Parse recommendation response"""
        response = response.replace('```json', '').replace('```', '').strip()
        start = response.find('{')
        end = response.rfind('}') + 1
        
        if start != -1 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        else:
            raise ValueError("No JSON found")
    
    def display_recommendation(self, recommendation: Dict):
        """Display recommendation"""
        print("\n" + "🎯 " + "=" * 66)
        print("YOUR PERSONALIZED NEXT PROBLEM RECOMMENDATION")
        print("=" * 70)
        
        print(f"\n📝 Problem #{recommendation.get('problem_number', 'N/A')}: {recommendation.get('problem_title', 'Unknown')}")
        print(f"🎚️  Difficulty: {recommendation.get('difficulty', 'Unknown')}")
        print(f"🔗 URL: {recommendation.get('leetcode_url', 'N/A')}")
        
        print(f"\n💡 Why this problem?")
        print(f"   {recommendation.get('why_recommended', 'Good for practice')}")
        
        print(f"\n🔑 Key Concepts:")
        for concept in recommendation.get('key_concepts', []):
            print(f"   • {concept}")
        
        print(f"\n⏱️  Estimated Time: {recommendation.get('estimated_time', 'Varies')}")
        
        hints = recommendation.get('hints', [])
        if hints:
            print(f"\n💭 Hints to get started:")
            for i, hint in enumerate(hints, 1):
                print(f"   {i}. {hint}")
        
        print("\n" + "=" * 70)
        print("🚀 Start solving: " + recommendation.get('leetcode_url', ''))
        print("=" * 70)
    
    def save_recommendation(self, recommendation: Dict, user_email: str = None):
        """Save recommendation to database"""
        try:
            conn = psycopg2.connect(self.neon_db_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO problem_recommendations 
                (problem_number, problem_title, difficulty, leetcode_url,
                 why_recommended, key_concepts, estimated_time, hints, user_email)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                recommendation.get('problem_number', 'N/A'),
                recommendation.get('problem_title', 'Unknown'),
                recommendation.get('difficulty', 'Unknown'),
                recommendation.get('leetcode_url', ''),
                recommendation.get('why_recommended', ''),
                recommendation.get('key_concepts', []),
                recommendation.get('estimated_time', ''),
                recommendation.get('hints', []),
                user_email
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Recommendation saved to database!")
        except Exception as e:
            print(f"⚠️ Could not save recommendation: {e}")


def main():
    """Run the automated system"""
    print("\n⚠️ IMPORTANT: This script should be imported, not run directly!")
    print("Please use: python run.py\n")


if __name__ == "__main__":
    main()