import os
import re
import requests
from typing import List, Dict, Any
import json
from pathlib import Path

class LeetCodeRepoAnalyzer:
    def __init__(self, github_token: str = None):
        """
        Initialize the analyzer with optional GitHub token for higher API rate limits
        
        Args:
            github_token: Personal access token from GitHub (optional but recommended)
        """
        self.github_token = github_token
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if github_token:
            self.headers['Authorization'] = f'token {github_token}'
    
    def parse_github_url(self, url: str) -> tuple:
        """
        Parse GitHub URL to extract owner and repo name
        
        Args:
            url: GitHub repository URL
            
        Returns:
            tuple: (owner, repo_name)
        """
        pattern = r'github\.com/([^/]+)/([^/]+)'
        match = re.search(pattern, url)
        if match:
            owner = match.group(1)
            repo = match.group(2).replace('.git', '')
            return owner, repo
        raise ValueError("Invalid GitHub URL format")
    
    def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """
        Get contents of a GitHub repository
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Path within the repository
            
        Returns:
            List of file/directory information
        """
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"Path not found: {path}")
            return []
        else:
            print(f"Error fetching contents: {response.status_code}")
            return []
    
    def get_file_content(self, download_url: str) -> str:
        """
        Download file content from GitHub
        
        Args:
            download_url: Direct download URL for the file
            
        Returns:
            File content as string
        """
        response = requests.get(download_url)
        if response.status_code == 200:
            return response.text
        return ""
    
    def is_code_file(self, filename: str) -> bool:
        """
        Check if file is a code file based on extension
        
        Args:
            filename: Name of the file
            
        Returns:
            True if it's a code file
        """
        code_extensions = ['.py', '.java', '.cpp', '.c', '.js', '.ts', '.go', 
                          '.rs', '.rb', '.php', '.swift', '.kt', '.cs', '.scala']
        return any(filename.endswith(ext) for ext in code_extensions)
    
    def extract_problem_info(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Extract problem information from filename and content
        
        Args:
            filename: Name of the file
            content: File content
            
        Returns:
            Dictionary with problem information
        """
        # Try to extract problem number from filename
        number_match = re.search(r'(\d+)', filename)
        problem_number = number_match.group(1) if number_match else "Unknown"
        
        # Try to extract problem title from filename or comments
        title = filename.replace('.py', '').replace('.java', '').replace('.cpp', '')
        title = re.sub(r'^\d+[-_.]?', '', title)  # Remove leading numbers
        title = title.replace('_', ' ').replace('-', ' ').title()
        
        # Try to find problem description in comments
        description = ""
        difficulty = "Unknown"
        
        # Look for common comment patterns
        comment_patterns = [
            r'"""(.*?)"""',  # Python docstrings
            r'/\*(.*?)\*/',  # Multi-line comments
            r'#\s*(.*?)(?:\n|$)',  # Python single-line comments
            r'//\s*(.*?)(?:\n|$)'  # Single-line comments
        ]
        
        for pattern in comment_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                description = matches[0].strip()
                break
        
        # Try to extract difficulty
        if 'easy' in content.lower() or 'easy' in filename.lower():
            difficulty = "Easy"
        elif 'medium' in content.lower() or 'medium' in filename.lower():
            difficulty = "Medium"
        elif 'hard' in content.lower() or 'hard' in filename.lower():
            difficulty = "Hard"
        
        return {
            'problem_number': problem_number,
            'title': title,
            'difficulty': difficulty,
            'description': description[:500] if description else "Not found in file",
            'filename': filename,
            'code': content,
            'language': self.get_language(filename)
        }
    
    def get_language(self, filename: str) -> str:
        """
        Determine programming language from file extension
        
        Args:
            filename: Name of the file
            
        Returns:
            Programming language name
        """
        extension_map = {
            '.py': 'Python',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.cs': 'C#',
            '.scala': 'Scala'
        }
        
        for ext, lang in extension_map.items():
            if filename.endswith(ext):
                return lang
        return "Unknown"
    
    def scan_repository(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """
        Recursively scan repository for code files
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Current path in repository
            
        Returns:
            List of problem information dictionaries
        """
        problems = []
        contents = self.get_repo_contents(owner, repo, path)
        
        for item in contents:
            if item['type'] == 'file' and self.is_code_file(item['name']):
                print(f"Processing: {item['path']}")
                file_content = self.get_file_content(item['download_url'])
                if file_content:
                    problem_info = self.extract_problem_info(item['name'], file_content)
                    problem_info['file_path'] = item['path']
                    problems.append(problem_info)
            
            elif item['type'] == 'dir':
                # Recursively scan subdirectories
                problems.extend(self.scan_repository(owner, repo, item['path']))
        
        return problems
    
    def analyze_repo(self, github_url: str) -> List[Dict]:
        """
        Main method to analyze a GitHub repository
        
        Args:
            github_url: Full GitHub repository URL
            
        Returns:
            List of extracted problem information
        """
        try:
            owner, repo = self.parse_github_url(github_url)
            print(f"Analyzing repository: {owner}/{repo}")
            
            problems = self.scan_repository(owner, repo)
            
            print(f"\nFound {len(problems)} LeetCode solutions!")
            return problems
            
        except Exception as e:
            print(f"Error analyzing repository: {str(e)}")
            return []
    
    def prepare_for_llm(self, problems: List[Dict]) -> str:
        """
        Prepare extracted data in a format suitable for LLM processing
        
        Args:
            problems: List of problem dictionaries
            
        Returns:
            Formatted string for LLM input
        """
        prompt = """Please analyze the following LeetCode solutions and organize them into a structured format suitable for database storage. For each solution, provide:

1. Problem Number
2. Problem Title
3. Difficulty Level
4. Programming Language
5. Code Quality Assessment (1-10)
6. Time Complexity
7. Space Complexity
8. Key Algorithms/Data Structures Used
9. Code Explanation
10. Potential Improvements

Here are the solutions to analyze:

"""
        
        for i, problem in enumerate(problems, 1):
            prompt += f"\n--- Solution {i} ---\n"
            prompt += f"File: {problem['filename']}\n"
            prompt += f"Path: {problem['file_path']}\n"
            prompt += f"Language: {problem['language']}\n"
            prompt += f"Extracted Number: {problem['problem_number']}\n"
            prompt += f"Extracted Title: {problem['title']}\n"
            prompt += f"\nCode:\n{problem['code']}\n"
            prompt += "-" * 50 + "\n"
        
        return prompt


def main():
    """
    Main function to run the analyzer
    """
    print("=== LeetCode GitHub Repository Analyzer ===\n")
    
    # Get GitHub token (optional but recommended)
    github_token = os.getenv('GITHUB_TOKEN')  # Set this in your environment
    
    # Initialize analyzer
    analyzer = LeetCodeRepoAnalyzer(github_token)
    
    # Get repository URL from user
    repo_url = input("Enter GitHub repository URL: ").strip()
    
    if not repo_url:
        print("No URL provided. Exiting.")
        return
    
    # Analyze repository
    problems = analyzer.analyze_repo(repo_url)
    
    if not problems:
        print("No LeetCode solutions found in the repository.")
        return
    
    # Save raw data to JSON
    output_file = 'leetcode_solutions_raw.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(problems, f, indent=2, ensure_ascii=False)
    print(f"\nRaw data saved to: {output_file}")
    
    # Prepare data for LLM
    llm_prompt = analyzer.prepare_for_llm(problems)
    
    # Save LLM prompt
    prompt_file = 'llm_prompt.txt'
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(llm_prompt)
    print(f"LLM prompt saved to: {prompt_file}")
    
    print("\n=== Next Steps ===")
    print("1. The raw data has been saved to 'leetcode_solutions_raw.json'")
    print("2. The LLM prompt has been saved to 'llm_prompt.txt'")
    print("3. Send the prompt to Gemini API to get structured analysis")
    print("4. Parse the LLM response and store in your database")


if __name__ == "__main__":
    main()