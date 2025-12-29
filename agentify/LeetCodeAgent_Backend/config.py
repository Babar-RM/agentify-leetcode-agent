"""
Automated LeetCode Analyzer - Config File Version
Just set your credentials once in config.json and run!
"""

import json
import os
from gemini_integration import AutomatedLeetCodeSystem

def load_config():
    """Load configuration from config.json"""
    config_file = 'config.json'
    
    # Create config file if doesn't exist
    if not os.path.exists(config_file):
        default_config = {
            "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
            "neon_db_url": "postgresql://user:pass@host/database",
            "github_token": ""
        }
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"✓ Created {config_file}")
        print("Please edit config.json with your credentials and run again!")
        return None
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Validate
    if config['gemini_api_key'] == "YOUR_GEMINI_API_KEY_HERE":
        print("❌ Please set your Gemini API key in config.json")
        return None
    
    if 'YOUR' in config['neon_db_url'] or 'user:pass' in config['neon_db_url']:
        print("❌ Please set your Neon database URL in config.json")
        return None
    
    return config

def main():
    """Main function with config file"""
    print("=" * 60)
    print("🚀 LEETCODE AUTOMATED ANALYZER")
    print("=" * 60)
    
    # Load config
    config = load_config()
    if not config:
        return
    
    # Get repository URL from user
    print("\nEnter GitHub Repository URL:")
    print("Example: https://github.com/username/leetcode-solutions")
    repo_url = input("URL: ").strip()
    
    if not repo_url:
        print("❌ Repository URL is required!")
        return
    
    # Initialize system
    system = AutomatedLeetCodeSystem(
        gemini_api_key=config['gemini_api_key'],
        neon_db_url=config['neon_db_url'],
        github_token=config.get('github_token') or None
    )
    
    # Process repository automatically
    system.process_repository(repo_url)
    
    print("\n✅ Done! Check your Neon database for the results.")

if __name__ == "__main__":
    main()