"""
Main Server - Run ALL backend servers with ONE command
Usage: python main.py
"""
import multiprocessing
import sys
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('MAIN')

# --- IMPORTANT: Change this block in your main.py ---

def run_api_server():
    """Run FastAPI server"""
    logger.info("🚀 Starting API Server on port 8000...")
    try:
        import uvicorn
        # CRITICAL FIX: Running Uvicorn using the string target prevents the config access crash 
        # that happens when passing the object directly in a new process.
        uvicorn.run("api_server:app", host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"❌ API Server failed: {e}")
        sys.exit(1)

def run_behavior_scheduler():
    """Run Behavior Email Scheduler"""
    logger.info("📧 Starting Behavior Email Scheduler (8 AM daily)...")
    try:
        # FIX 1: Correct the class name from DailyScheduler to DailyProblemScheduler
        from daily_scheduler import DailyProblemScheduler
        
        # FIX 2: Schedulers should just read config from the file, or expect a flat structure.
        # Since the scheduler classes are designed to read config.json internally (in __init__),
        # we will initialize them without arguments.
        scheduler = DailyProblemScheduler() 
        
        # Start scheduler (sends at 8 AM)
        scheduler.start_scheduler() # Assuming start_scheduler handles the 08:00 time internally
        
    except Exception as e:
        logger.error(f"❌ Behavior Scheduler failed: {e}")
        # Print traceback to debug import errors
        import traceback
        traceback.print_exc()
        sys.exit(1)

def run_course_scheduler():
    """Run Course Email Scheduler"""
    logger.info("📚 Starting Course Email Scheduler (9 AM daily)...")
    try:
        # FIX 3: Initialize CourseEmailScheduler without arguments
        from course_email_scheduler import CourseEmailScheduler
        
        scheduler = CourseEmailScheduler()
        
        # Start scheduler (sends at 9 AM)
        scheduler.start() # CourseEmailScheduler uses .start()
        
    except Exception as e:
        logger.error(f"❌ Course Scheduler failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
def check_prerequisites():
    """Check if all prerequisites are met"""
    logger.info("🔍 Checking prerequisites...")
    
    # Check config file exists
    if not Path('config.json').exists():
        logger.error("❌ config.json not found! Please create it first.")
        return False
    
    # Check if required Python packages are installed
    required_packages = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'psycopg2': 'psycopg2-binary',
        'pydantic': 'pydantic',
        # REMOVED 'google.generativeai': 'google-generativeai'
        'schedule': 'schedule'
    }
    
    missing_packages = []
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name.replace('-', '_').replace('.', '_'))
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        logger.error(f"❌ Missing packages: {', '.join(missing_packages)}")
        logger.error("   Install with: pip install -r requirements.txt")
        return False
    
    # Check database connection (This will now run reliably)
    try:
        import json
        import psycopg2
        
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # This check is now necessary to ensure the config structure is correct.
        # It relies on the nested 'database' structure (or will crash if the structure is flat).
        conn = psycopg2.connect(
            host=config['database']['host'],
            dbname=config['database']['dbname'],
            user=config['database']['user'],
            password=config['database']['password'],
            sslmode=config['database']['sslmode']
        )
        conn.close()
        logger.info("✅ Database connection successful")
    except KeyError as e:
        logger.error(f"❌ Config error: Missing required key {e} in config.json. Did you update to the nested structure?")
        return False
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error("   Make sure PostgreSQL is running and config.json is correct")
        return False
    
    logger.info("✅ All prerequisites met!")
    return True

def main():
    """Main function to start all servers"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║         🤖 AGENTIFY LEETCODE AGENT BACKEND 🤖              ║
    ║                                                            ║
    ║         Starting All Services...                           ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Check prerequisites
    if not check_prerequisites():
        logger.error("❌ Prerequisites check failed. Exiting...")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("🚀 Starting all backend services...")
    logger.info("=" * 60)
    
    # Create processes for each server
    processes = []
    
    try:
        # Process 1: API Server
        api_process = multiprocessing.Process(target=run_api_server, name="API-Server")
        api_process.start()
        processes.append(api_process)
        time.sleep(2)  # Wait for API to start
        
        # Process 2: Behavior Scheduler
        behavior_process = multiprocessing.Process(target=run_behavior_scheduler, name="Behavior-Scheduler")
        behavior_process.start()
        processes.append(behavior_process)
        time.sleep(1)
        
        # Process 3: Course Scheduler
        course_process = multiprocessing.Process(target=run_course_scheduler, name="Course-Scheduler")
        course_process.start()
        processes.append(course_process)
        time.sleep(1)
        
        logger.info("=" * 60)
        logger.info("✅ ALL SERVICES STARTED SUCCESSFULLY!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("📌 Services Running:")
        logger.info("   • API Server:           http://localhost:8000")
        logger.info("   • API Docs:             http://localhost:8000/docs")
        logger.info("   • Behavior Scheduler:   Sending emails at 8 AM daily")
        logger.info("   • Course Scheduler:     Sending emails at 9 AM daily")
        logger.info("")
        logger.info("🌐 Next Steps:")
        logger.info("   1. Open your Next.js frontend: cd ../agentify-leetcode-agent")
        logger.info("   2. Start frontend: npm run dev")
        logger.info("   3. Open browser: http://localhost:3000")
        logger.info("")
        logger.info("⚠️  Press Ctrl+C to stop all services")
        logger.info("=" * 60)
        
        # Keep main process alive and monitor child processes
        while True:
            time.sleep(1)
            
            # Check if any process died
            for process in processes:
                if not process.is_alive():
                    logger.error(f"❌ Process {process.name} died! Restarting all services...")
                    raise Exception(f"{process.name} stopped unexpectedly")
    
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("⚠️  Shutdown signal received...")
        logger.info("=" * 60)
        
        # Terminate all processes
        for process in processes:
            logger.info(f"🛑 Stopping {process.name}...")
            process.terminate()
            process.join(timeout=5)
            
            if process.is_alive():
                logger.warning(f"⚠️  {process.name} didn't stop gracefully, forcing...")
                process.kill()
        
        logger.info("=" * 60)
        logger.info("✅ All services stopped successfully!")
        logger.info("=" * 60)
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        
        # Terminate all processes
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        
        sys.exit(1)

if __name__ == "__main__":
    # Required for Windows
    multiprocessing.freeze_support()
    main()