"""
FastAPI Backend Server for LeetCode Analyzer
Complete REST API with Course Management
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime, date
from gemini_integration import AutomatedLeetCodeSystem
from course_service import CourseService
import uvicorn

# ==================== LOAD CONFIGURATION ====================
print("Loading configuration...")
with open('config.json', 'r') as f:
    config = json.load(f)

print("✅ Configuration loaded")

# CRITICAL FIX: Reconstruct the full DB URL from the nested 'database' config
DB_URL = f"postgresql://{config['database']['user']}:{config['database']['password']}@{config['database']['host']}:{config['database']['port']}/{config['database']['dbname']}?sslmode={config['database']['sslmode']}"

# ==================== INITIALIZE FASTAPI ====================
app = FastAPI(
    title="LeetCode Analyzer API",
    description="Backend API for LeetCode solution analyzer with company courses",
    version="2.0.0"
)

# ==================== CORS MIDDLEWARE (omitted for brevity) ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js default
        "http://localhost:3001",
        "http://localhost:5173",  # Vite default
        "https://your-frontend-domain.com"  # Production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== INITIALIZE SERVICES ====================
print("Initializing services...")
# FIX: Use the reconstructed DB_URL
course_service = CourseService(DB_URL)
print("✅ Course service initialized")

# ==================== PYDANTIC MODELS (omitted for brevity) ====================

class AnalyzeRequest(BaseModel):
    github_url: str
    email: EmailStr

class SubscribeRequest(BaseModel):
    email: EmailStr
    company_slug: str
    payment_id: Optional[str] = None

class CompleteRequest(BaseModel):
    email: EmailStr
    company_slug: str
    problem_number: str

# ==================== DATABASE HELPER ====================

def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# ==================== BACKGROUND TASKS ====================

def analyze_repository_background(github_url: str, email: str):
    """Background task to analyze repository"""
    try:
        system = AutomatedLeetCodeSystem(
            gemini_api_key=config['gemini_api_key'],
            neon_db_url=DB_URL,
            github_token=config.get('github_token'),
            brevo_api_key=config['email']['api_key'],
            brevo_sender_email=config['email']['sender_email'],
            brevo_sender_name=config['email']['sender_name']
        )
        
        # Ensure email is lowercase for consistency
        system.process_repository(github_url, email.lower())
        print(f"✅ Analysis completed for {email}")
    except Exception as e:
        print(f"❌ Error analyzing repository: {e}")

# ==================== ENDPOINTS ====================

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/health")
def health_check():
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")

@app.post("/api/analyze")
async def analyze_repository(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(
            analyze_repository_background,
            request.github_url,
            request.email.lower() # Normalize email immediately
        )
        return {
            "message": "Analysis started",
            "status": "processing",
            "email": request.email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{email}")
def get_user(email: str):
    """Get user information (CASE INSENSITIVE)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # FIX: Use LOWER() for case-insensitive lookup
        cursor.execute("""
            SELECT email, github_username, github_repo_url, 
                   total_problems_analyzed, registration_date, is_active
            FROM users
            WHERE LOWER(email) = LOWER(%s)
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            # 404 is correct if user truly doesn't exist
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "email": user['email'],
            "github_username": user['github_username'],
            "github_repo_url": user['github_repo_url'],
            "total_problems_analyzed": user['total_problems_analyzed'],
            "registration_date": str(user['registration_date']),
            "is_active": user['is_active']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/solutions/{email}")
def get_user_solutions(email: str, limit: int = 100, offset: int = 0):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, problem_number, problem_title, difficulty, language,
                   time_complexity, space_complexity, algorithms, 
                   data_structures, explanation, tags, created_at
            FROM leetcode_solutions
            WHERE user_email = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (email, limit, offset))
        
        solutions = cursor.fetchall()
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM leetcode_solutions
            WHERE user_email = %s
        """, (email,))
        
        total = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "solutions": [
                {
                    "id": s['id'],
                    "problem_number": s['problem_number'],
                    "problem_title": s['problem_title'],
                    "difficulty": s['difficulty'],
                    "language": s['language'],
                    "time_complexity": s['time_complexity'],
                    "space_complexity": s['space_complexity'],
                    "algorithms": s['algorithms'] or [],
                    "data_structures": s['data_structures'] or [],
                    "explanation": s['explanation'],
                    "tags": s['tags'] or [],
                    "created_at": str(s['created_at'])
                }
                for s in solutions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/{email}")
def get_user_stats(email: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE difficulty = 'Easy') as easy,
                COUNT(*) FILTER (WHERE difficulty = 'Medium') as medium,
                COUNT(*) FILTER (WHERE difficulty = 'Hard') as hard,
                ARRAY_AGG(DISTINCT language) as languages
            FROM leetcode_solutions
            WHERE user_email = %s
        """, (email,))
        
        stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'pending') as pending
            FROM problem_recommendations
            WHERE user_email = %s
        """, (email,))
        
        recs = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return {
            "total_solutions": stats['total'] or 0,
            "easy_count": stats['easy'] or 0,
            "medium_count": stats['medium'] or 0,
            "hard_count": stats['hard'] or 0,
            "languages": [l for l in (stats['languages'] or []) if l],
            "total_recommendations": recs['total'] or 0,
            "pending_recommendations": recs['pending'] or 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses")
def get_courses():
    try:
        courses = course_service.get_all_courses()
        return {
            "courses": courses,
            "total": len(courses)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses/{company_slug}")
def get_course_details(company_slug: str):
    try:
        course = course_service.get_course_details(company_slug)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/subscribe")
def subscribe_to_course(request: SubscribeRequest):
    try:
        result = course_service.subscribe_user(
            request.email,
            request.company_slug,
            request.payment_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/my-courses/{email}")
def get_user_courses(email: str):
    try:
        subscriptions = course_service.get_user_subscriptions(email)
        return {
            "subscriptions": subscriptions,
            "total": len(subscriptions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/course-progress/{email}/{company_slug}")
def get_progress(email: str, company_slug: str):
    try:
        progress = course_service.get_progress(email, company_slug)
        if not progress:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return progress
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mark-completed")
def mark_completed(request: CompleteRequest):
    try:
        success = course_service.mark_completed(
            request.email,
            request.company_slug,
            request.problem_number
        )
        
        if success:
            return {"message": "Problem marked as completed", "success": True}
        else:
            raise HTTPException(status_code=404, detail="Problem or subscription not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== RUN SERVER ====================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 STARTING LEETCODE ANALYZER API SERVER")
    print("=" * 70)
    print("\n📡 Available Endpoints:")
    print("   • GET    /                          - API Info")
    print("   • GET    /health                    - Health Check")
    print("   • GET    /docs                      - API Documentation")
    print("\n   GitHub Analysis:")
    print("   • POST   /api/analyze               - Analyze GitHub repo")
    print("   • GET    /api/user/{email}          - Get user info")
    print("   • GET    /api/solutions/{email}     - Get solutions")
    print("   • GET    /api/stats/{email}         - Get statistics")
    print("\n   Company Courses:")
    print("   • GET    /api/courses               - Get all courses")
    print("   • GET    /api/courses/{slug}        - Get course details")
    print("   • POST   /api/subscribe             - Subscribe to course")
    print("   • GET    /api/my-courses/{email}    - Get user's courses")
    print("   • GET    /api/course-progress/{email}/{slug} - Get progress")
    print("   • POST   /api/mark-completed        - Mark problem done")
    print("\n📖 API Documentation: http://localhost:8000/docs")
    print("=" * 70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)