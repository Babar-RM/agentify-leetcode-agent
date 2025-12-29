"""
Course Management Service
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class CourseService:
    def __init__(self, db_url_flat: str):
        # The constructor receives the reconstructed DB_URL string from api_server.py
        self.db_url = db_url_flat
    
    def get_db(self):
        # FIX: Use the db_url string
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
    
    # ... (rest of the file remains the same, assuming logic is fine) ...

    def get_all_courses(self) -> List[Dict]:
        """Get all courses"""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, slug, description, logo_url,
                   course_price, duration_days, total_problems
            FROM companies WHERE is_active = TRUE
            ORDER BY name
        """)
        
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(c) for c in courses]
    
    def get_course_details(self, slug: str) -> Optional[Dict]:
        """Get course details"""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.*, 
                   COUNT(cp.id) as actual_problems,
                   json_agg(
                       json_build_object(
                           'number', cp.problem_number,
                           'title', cp.problem_title,
                           'difficulty', cp.difficulty,
                           'day', cp.day_number
                       ) ORDER BY cp.day_number
                   ) as problems
            FROM companies c
            LEFT JOIN company_problems cp ON c.id = cp.company_id
            WHERE c.slug = %s AND c.is_active = TRUE
            GROUP BY c.id
        """, (slug,))
        
        course = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(course) if course else None
    
    def subscribe_user(self, email: str, slug: str, payment_id: str = None) -> Dict:
        """Subscribe user to course"""
        conn = self.get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT id, duration_days, course_price FROM companies WHERE slug = %s",
                (slug,)
            )
            company = cursor.fetchone()
            
            if not company:
                raise ValueError("Course not found")
            
            company_id = company['id']
            expiry = datetime.now() + timedelta(days=company['duration_days'])
            
            cursor.execute(
                "SELECT COUNT(*) as total FROM company_problems WHERE company_id = %s",
                (company_id,)
            )
            total = cursor.fetchone()['total']
            
            cursor.execute("""
                INSERT INTO course_subscriptions 
                (user_email, company_id, expiry_date, payment_id, 
                 amount_paid, status, payment_status, progress)
                VALUES (%s, %s, %s, %s, %s, 'active', 'completed', %s)
                ON CONFLICT (user_email, company_id) 
                DO UPDATE SET 
                    expiry_date = EXCLUDED.expiry_date,
                    status = 'active',
                    subscription_date = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                email, company_id, expiry, payment_id,
                company['course_price'],
                json.dumps({'completed': 0, 'total': total, 'current_day': 1})
            ))
            
            sub_id = cursor.fetchone()['id']
            
            # Schedule emails
            self._schedule_emails(cursor, sub_id, company_id)
            
            conn.commit()
            
            return {
                'subscription_id': sub_id,
                'company_slug': slug,
                'status': 'active',
                'expiry_date': str(expiry),
                'total_problems': total
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def _schedule_emails(self, cursor, sub_id: int, company_id: int):
        """Schedule daily emails"""
        cursor.execute("""
            SELECT id, day_number FROM company_problems
            WHERE company_id = %s ORDER BY day_number
        """, (company_id,))
        
        problems = cursor.fetchall()
        start = datetime.now().date() + timedelta(days=1)
        
        for prob in problems:
            date = start + timedelta(days=prob['day_number'] - 1)
            cursor.execute("""
                INSERT INTO course_email_schedule 
                (subscription_id, problem_id, scheduled_date)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (sub_id, prob['id'], date))
    
    def get_user_subscriptions(self, email: str) -> List[Dict]:
        """Get user's subscriptions"""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cs.*, c.name, c.slug, c.logo_url, c.duration_days
            FROM course_subscriptions cs
            JOIN companies c ON cs.company_id = c.id
            WHERE cs.user_email = %s
            ORDER BY cs.subscription_date DESC
        """, (email,))
        
        subs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(s) for s in subs]
    
    def get_progress(self, email: str, slug: str) -> Dict:
        """Get course progress"""
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                cs.progress,
                COUNT(ucp.id) as attempted,
                COUNT(CASE WHEN ucp.status = 'completed' THEN 1 END) as completed,
                cs.subscription_date,
                cs.expiry_date,
                cs.status
            FROM course_subscriptions cs
            LEFT JOIN user_course_progress ucp ON cs.id = ucp.subscription_id
            JOIN companies c ON cs.company_id = c.id
            WHERE cs.user_email = %s AND c.slug = %s
            GROUP BY cs.id
        """, (email, slug))
        
        prog = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(prog) if prog else None
    
    def mark_completed(self, email: str, slug: str, prob_num: str) -> bool:
        """Mark problem completed"""
        conn = self.get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT cs.id as sub_id, cp.id as prob_id
                FROM course_subscriptions cs
                JOIN companies c ON cs.company_id = c.id
                JOIN company_problems cp ON cp.company_id = c.id
                WHERE cs.user_email = %s AND c.slug = %s AND cp.problem_number = %s
            """, (email, slug, prob_num))
            
            result = cursor.fetchone()
            if not result:
                return False
            
            cursor.execute("""
                INSERT INTO user_course_progress 
                (subscription_id, problem_id, user_email, status, solved_at)
                VALUES (%s, %s, %s, 'completed', CURRENT_TIMESTAMP)
                ON CONFLICT (subscription_id, problem_id) 
                DO UPDATE SET status = 'completed', solved_at = CURRENT_TIMESTAMP
            """, (result['sub_id'], result['prob_id'], email))
            
            cursor.execute("""
                UPDATE course_subscriptions
                SET progress = jsonb_set(
                    progress, '{completed}',
                    (COALESCE((progress->>'completed')::int, 0) + 1)::text::jsonb
                )
                WHERE id = %s
            """, (result['sub_id'],))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()