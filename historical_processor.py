#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Historical Git Repository Processor

This script performs one-time historical processing of git repositories:
- Clones bare repository to get all historical data
- Processes all commits using EXACT same logic as git-integration
- Extracts maintainer information using git show
- Stores processed commits and contributors in files
- Logs processing time, debug info, and file sizes
- Tracks latest commit hash to avoid reprocessing
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import shutil
import datetime
import re
import hashlib
from datetime import timezone
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Add the crowdgit module to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crowdgit.activitymap import ActivityMap
from crowdgit.cm_maintainers_data.scraper import analyze_file_content
from crowdgit.activity import extract_activities, prepare_crowd_activities

# Import original functions for exact compatibility
from crowdgit.repo import (
    is_valid_commit_hash, 
    is_valid_datetime, 
    store_bad_commits,
    get_default_branch
)

try:
    import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class HistoricalProcessor:
    """Main class for processing git repositories historically"""
    
    def __init__(self, remote_url: str, output_dir: str = "historical_output"):
        self.remote_url = remote_url
        self.repo_name = self._get_repo_name(remote_url)
        self.output_dir = Path(output_dir)
        self.repo_dir = self.output_dir / f"{self.repo_name}.git"
        
        # Create output directories
        self.output_dir.mkdir(exist_ok=True)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.data_dir = self.output_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # File paths for storing results
        self.commits_file = self.data_dir / f"{self.repo_name}_commits.json"
        self.contributors_file = self.data_dir / f"{self.repo_name}_contributors.json"
        self.maintainers_file = self.data_dir / f"{self.repo_name}_maintainers.json"
        self.activities_file = self.data_dir / f"{self.repo_name}_activities.json"
        self.state_file = self.data_dir / f"{self.repo_name}_state.json"
        
        # Processing stats
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_commits': 0,
            'processed_commits': 0,
            'contributors_found': 0,
            'maintainers_found': 0,
            'activities_found': 0,
            'file_sizes': {},
            'processing_errors': 0
        }

    def _get_repo_name(self, remote_url: str) -> str:
        """Extract repository name from remote URL"""
        # Remove .git suffix and extract name
        name = remote_url.rstrip('/').split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        # Replace invalid characters for filenames
        return re.sub(r'[^\w\-_.]', '_', name)

    def _setup_logging(self) -> logging.Logger:
        """Setup detailed logging with file and console output"""
        logger = logging.getLogger(f'historical_processor_{self.repo_name}')
        logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # File handler for detailed logs
        log_file = self.logs_dir / f"{self.repo_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for important messages
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def _get_file_size(self, file_path: Path) -> int:
        """Get file size in bytes"""
        try:
            return file_path.stat().st_size if file_path.exists() else 0
        except Exception:
            return 0

    def _get_directory_size(self, dir_path: Path) -> int:
        """Get total size of directory in bytes"""
        try:
            if not dir_path.exists():
                return 0
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    try:
                        total_size += filepath.stat().st_size
                    except Exception:
                        continue
            return total_size
        except Exception:
            return 0

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _log_file_sizes(self, stage: str):
        """Log current file sizes"""
        sizes = {
            'repo_directory': self._get_directory_size(self.repo_dir),
            'commits_file': self._get_file_size(self.commits_file),
            'contributors_file': self._get_file_size(self.contributors_file),
            'maintainers_file': self._get_file_size(self.maintainers_file),
            'activities_file': self._get_file_size(self.activities_file),
            'state_file': self._get_file_size(self.state_file),
            'total_output': self._get_directory_size(self.output_dir)
        }
        
        self.stats['file_sizes'][stage] = sizes
        
        self.logger.info(f"=== File Sizes at {stage} ===")
        for name, size in sizes.items():
            self.logger.info(f"{name}: {self._format_size(size)} ({size:,} bytes)")

    def _run_git_command(self, cmd: List[str], cwd: str = None) -> Tuple[bool, str]:
        """Run git command and return success status and output."""
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd or str(self.repo_dir),
                capture_output=True, 
                text=True, 
                check=True
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {' '.join(cmd)}")
            self.logger.error(f"Error: {e.stderr}")
            return False, e.stderr

    def check_already_processed(self) -> bool:
        """Check if repository has already been processed"""
        if not self.state_file.exists():
            return False
            
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            if state.get('processing_complete', False):
                self.logger.info(f"Repository {self.repo_name} already processed")
                self.logger.info(f"Last processed: {state.get('completion_time')}")
                self.logger.info(f"Total commits processed: {state.get('total_commits', 0)}")
                return True
                
        except Exception as e:
            self.logger.warning(f"Error reading state file: {e}")
            
        return False

    def clone_repository(self) -> bool:
        """Clone bare repository for processing"""
        if self.repo_dir.exists():
            self.logger.info(f"Repository directory already exists: {self.repo_dir}")
            return True
            
        self.logger.info(f"Cloning repository: {self.remote_url}")
        start_time = time.time()
        
        try:
            # Clone bare repository
            cmd = ['git', 'clone', '--bare', self.remote_url, str(self.repo_dir)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            clone_time = time.time() - start_time
            self.logger.info(f"Repository cloned successfully in {clone_time:.2f} seconds")
            
            # Log initial sizes
            self._log_file_sizes("after_clone")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to clone repository: {e}")
            self.logger.error(f"Command output: {e.stderr}")
            return False

    def get_commits(self, verbose: bool = False) -> List[Dict]:
        """
        Get all commits using EXACT same logic as original git-integration get_commits function.
        Only difference: adapted for bare repository (no working directory).
        """
        self.logger.info("Extracting commits from %s", self.repo_dir)
        
        # For bare repository, we use HEAD instead of origin/branch
        commit_range = "HEAD"
        
        splitter = "--CROWD-END-OF-COMMIT--"
        
        git_log_command = [
            "git",
            "-C",
            str(self.repo_dir),
            "log",
            commit_range,
            f"--pretty=format:%H%n%aI%n%an%n%ae%n%cI%n%cn%n%ce%n%P%n%d%n%B%n{splitter}",
        ]
        
        # Set core.abbrevCommit to false to avoid truncating commit messages
        subprocess.check_output(["git", "-C", str(self.repo_dir), "config", "core.abbrevCommit", "false"])
        
        start_time = time.time()
        try:
            commits_output = (
                subprocess.check_output(git_log_command).decode("utf-8", errors="replace").strip()
            )
        except Exception as e:
            self.logger.error(
                "Failed trying to extract commits for %s with %s: \n%s",
                self.repo_dir,
                " ".join(git_log_command),
                str(e),
            )
            return []
        
        end_time = time.time()
        
        if not commits_output:
            self.logger.info("Did not find any commit output in %s", self.repo_dir)
            return []
        
        bad_commits = 0
        commits = []
        
        commits_texts = commits_output.split(splitter)
        if verbose and HAS_TQDM:
            commits_iter = tqdm.tqdm(commits_texts, desc="Parsing commits")
        else:
            commits_iter = commits_texts
        
        for commit_text in commits_iter:
            commit_lines = commit_text.strip().splitlines()
            
            if len(commit_lines) < 8:
                bad_commits += 1
                store_bad_commits(commit_text, str(self.repo_dir))
                continue
            
            if (len(commit_lines)) < 9:
                from pprint import pprint as pp
                pp(commit_lines)
            
            commit_hash = commit_lines[0]
            author_datetime = commit_lines[1]
            author_name = commit_lines[2]
            author_email = commit_lines[3]
            
            # Check for empty author email
            if author_email is None or author_email.strip() == "":
                bad_commits += 1
                store_bad_commits(commit_text, str(self.repo_dir))
                continue
            
            commit_datetime = commit_lines[4]
            commit_datetime_obj = datetime.datetime.strptime(commit_datetime, "%Y-%m-%dT%H:%M:%S%z")
            if commit_datetime_obj > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                days=1
            ):
                commit_datetime = author_datetime
            committer_name = commit_lines[5]
            committer_email = commit_lines[6]
            parent_hashes = commit_lines[7].split()
            if len(commit_lines) >= 9:
                ref_names = commit_lines[8].strip()
            else:
                ref_names = ""
            
            if len(commit_lines) >= 10:
                commit_message = commit_lines[9:]
            else:
                commit_message = ""
            
            if not (is_valid_commit_hash(commit_hash) and is_valid_datetime(commit_datetime)):
                self.logger.error(
                    "Invalid commit data found: hash=%s, datetime=%s",
                    commit_hash,
                    commit_datetime,
                )
                bad_commits += 1
                store_bad_commits(commit_text, str(self.repo_dir))
                continue
            
            is_merge_commit = len(parent_hashes) > 1
            is_main_branch = True
            
            commits.append(
                {
                    "hash": commit_hash,
                    "author_datetime": author_datetime,
                    "author_name": author_name,
                    "author_email": author_email,
                    "committer_datetime": commit_datetime,
                    "committer_name": committer_name,
                    "committer_email": committer_email,
                    "is_main_branch": is_main_branch,
                    "is_merge_commit": is_merge_commit,
                    "message": commit_message,
                }
            )
        
        self.logger.info(
            "%d commits extracted from %s in %d s (%.1f min), %d bad commits",
            len(commits),
            self.repo_dir,
            int(end_time - start_time),
            (end_time - start_time) / 60,
            bad_commits,
        )
        
        self.stats['total_commits'] = len(commits)
        return commits

    def get_insertions_deletions(self, verbose: bool = False) -> Dict[str, Dict]:
        """
        Get insertions and deletions using EXACT same logic as original git-integration.
        Only difference: adapted for bare repository.
        """
        self.logger.info("Extracting insertions/deletions from %s", self.repo_dir)
        
        # For bare repository, we use HEAD instead of origin/branch
        commit_range = "HEAD"
        
        git_log_command = [
            "git",
            "-C",
            str(self.repo_dir),
            "log",
            commit_range,
            "--pretty=format:%H",
            "--cc",
            "--numstat",
        ]
        
        # Set core.abbrevCommit to false to avoid truncating commit messages
        subprocess.check_output(["git", "-C", str(self.repo_dir), "config", "core.abbrevCommit", "false"])
        
        start_time = time.time()
        try:
            commits_output = (
                subprocess.check_output(git_log_command).decode("utf-8", errors="replace").strip()
            )
        except:
            return {}
        
        end_time = time.time()
        
        if not commits_output:
            return {}
        
        bad_commits = 0
        changes = {}
        
        commits_texts = commits_output.split("\n\n")
        if verbose and HAS_TQDM:
            commits_iter = tqdm.tqdm(commits_texts, desc="Extracting insertions/deletions")
        else:
            commits_iter = commits_texts
        
        for commit_text in commits_iter:
            commit_lines = commit_text.strip().splitlines()
            
            if len(commit_lines) < 2:
                bad_commits += 1
                store_bad_commits(commit_text, str(self.repo_dir))
                continue
            
            commit_hash = commit_lines[0]
            if not is_valid_commit_hash(commit_hash):
                self.logger.error("Invalid insertions/deletions hash found: hash=%s", commit_hash)
                bad_commits += 1
                store_bad_commits(commit_text, str(self.repo_dir))
                continue
            
            insertions_deletions = commit_lines[1:]
            insertions = 0
            deletions = 0
            
            for line in insertions_deletions:
                match = re.match(r"^(\d+)\s+(\d+)", line)
                if match:
                    insertions += int(match.group(1))
                    deletions += int(match.group(2))
            
            changes[commit_hash] = {"insertions": insertions, "deletions": deletions}
        
        end_time = time.time()
        
        self.logger.info(
            "Changes for %d commits extracted from %s in %d s (%.1f min), %d bad commits",
            len(changes),
            self.repo_dir,
            int(end_time - start_time),
            (end_time - start_time) / 60,
            bad_commits,
        )
        
        return changes

    def add_insertions_deletions(self, commits: List, insertions_deletions: Dict) -> List[Dict]:
        """Add insertions/deletions to commits - same logic as original"""
        return [
            commit | insertions_deletions.get(commit["hash"], {"insertions": 0, "deletions": 0})
            for commit in commits
        ]

    def get_file_content_at_commit(self, commit_hash: str, file_path: str) -> Optional[str]:
        """Get file content at specific commit using git show"""
        try:
            cmd = [
                'git', '-C', str(self.repo_dir), 'show',
                f"{commit_hash}:{file_path}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
            
        except subprocess.CalledProcessError:
            return None

    def find_maintainer_files_at_commit(self, commit_hash: str) -> List[Tuple[str, str]]:
        """Find maintainer files at specific commit using git ls-tree"""
        maintainer_files = [
            'MAINTAINERS', 'MAINTAINERS.md', 'MAINTAINERS.txt',
            'CODEOWNERS', '.github/CODEOWNERS', 'docs/CODEOWNERS',
            'OWNERS', 'OWNERS.md', 'maintainers.yaml', 'maintainers.yml'
        ]
        
        found_files = []
        
        try:
            # List all files in the commit
            cmd = ['git', '-C', str(self.repo_dir), 'ls-tree', '-r', '--name-only', commit_hash]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            all_files = result.stdout.strip().split('\n')
            
            for maintainer_file in maintainer_files:
                if maintainer_file in all_files:
                    content = self.get_file_content_at_commit(commit_hash, maintainer_file)
                    if content:
                        found_files.append((maintainer_file, content))
                        
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Error listing files for commit {commit_hash}: {e}")
            
        return found_files

    def process_commits(self, verbose: bool = False) -> Tuple[List[Dict], List[Dict], Dict]:
        """Process all commits using EXACT same logic as git-integration"""
        self.logger.info("Processing commits with exact git-integration logic")
        
        # Step 1: Get commits using exact same logic
        commits = self.get_commits(verbose=verbose)
        if not commits:
            self.logger.error("No commits found in repository")
            return [], [], {}
        
        # Step 2: Get insertions/deletions using exact same logic
        insertions_deletions = self.get_insertions_deletions(verbose=verbose)
        
        # Step 3: Add insertions/deletions to commits using exact same logic
        commits_with_changes = self.add_insertions_deletions(commits, insertions_deletions)
        
        # Step 4: Prepare crowd activities using exact same logic
        self.logger.info("Preparing crowd activities")
        activities = prepare_crowd_activities(self.remote_url, commits_with_changes, verbose=verbose)
        
        # Step 5: Extract contributors from commits (same as original logic)
        contributors = {}
        for commit in commits_with_changes:
            author_email = commit['author_email']
            committer_email = commit['committer_email']
            
            # Track author
            if author_email not in contributors:
                contributors[author_email] = {
                    'name': commit['author_name'],
                    'email': author_email,
                    'commits_authored': 0,
                    'commits_committed': 0,
                    'first_commit': commit['author_datetime'],
                    'last_commit': commit['author_datetime']
                }
            
            contributors[author_email]['commits_authored'] += 1
            contributors[author_email]['last_commit'] = commit['author_datetime']
            
            # Track committer if different
            if committer_email != author_email:
                if committer_email not in contributors:
                    contributors[committer_email] = {
                        'name': commit['committer_name'],
                        'email': committer_email,
                        'commits_authored': 0,
                        'commits_committed': 0,
                        'first_commit': commit['committer_datetime'],
                        'last_commit': commit['committer_datetime']
                    }
                contributors[committer_email]['commits_committed'] += 1
        
        self.stats['processed_commits'] = len(commits_with_changes)
        self.stats['contributors_found'] = len(contributors)
        self.stats['activities_found'] = len(activities)
        
        self.logger.info(f"Processed {len(commits_with_changes)} commits")
        self.logger.info(f"Found {len(contributors)} unique contributors")
        self.logger.info(f"Generated {len(activities)} activities")
        
        return commits_with_changes, activities, contributors

    def _extract_maintainers(self) -> List[Dict]:
        """Extract maintainer information from latest version (following git-integration approach)."""
        maintainers = []
        maintainer_files = [
            'MAINTAINERS',
            'MAINTAINERS.md', 
            'MAINTAINER.md',
            'CODEOWNERS',
            '.github/CODEOWNERS',
            'CODEOWNERS.md',
            'CONTRIBUTORS',
            'CONTRIBUTORS.md',
            'docs/MAINTAINERS.md',
            'OWNERS',
            '.github/MAINTAINERS.md',
            '.github/CONTRIBUTORS.md'
        ]
        
        logger.info("Extracting maintainer information from latest version...")
        
        # Use the latest commit from the main branch (same as git-integration approach)
        for filename in maintainer_files:
            success, content = self._run_git_command([
                'git', 'show', f'HEAD:{filename}'
            ])
            
            if success and content:
                logger.info(f"Found maintainer file: {filename}")
                # Simple maintainer extraction (can be enhanced with AI like git-integration)
                for line in content.split('\n'):
                    line = line.strip()
                    if '@' in line and not line.startswith('#'):
                        # Extract email addresses
                        import re
                        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                        for email in emails:
                            maintainers.append({
                                'email': email,
                                'file': filename,
                                'line': line
                            })
                # Only process the first maintainer file found (like git-integration)
                break
        
        logger.info(f"Found {len(maintainers)} maintainer entries")
        return maintainers

    def save_results(self, commits: List[Dict], activities: List[Dict], contributors: Dict, maintainers: Dict):
        """Save processing results to files"""
        self.logger.info("Saving results to files")
        
        try:
            # Save commits
            with open(self.commits_file, 'w', encoding='utf-8') as f:
                json.dump(commits, f, indent=2, ensure_ascii=False)
            
            # Save activities
            with open(self.activities_file, 'w', encoding='utf-8') as f:
                json.dump(activities, f, indent=2, ensure_ascii=False)
            
            # Save contributors
            with open(self.contributors_file, 'w', encoding='utf-8') as f:
                json.dump(contributors, f, indent=2, ensure_ascii=False)
            
            # Save maintainers
            with open(self.maintainers_file, 'w', encoding='utf-8') as f:
                json.dump(maintainers, f, indent=2, ensure_ascii=False)
            
            # Save processing state
            state = {
                'repository_url': self.remote_url,
                'repository_name': self.repo_name,
                'processing_complete': True,
                'completion_time': datetime.datetime.now(timezone.utc).isoformat(),
                'total_commits': self.stats['total_commits'],
                'processed_commits': self.stats['processed_commits'],
                'contributors_found': self.stats['contributors_found'],
                'maintainers_found': self.stats['maintainers_found'],
                'activities_found': self.stats['activities_found'],
                'processing_errors': self.stats['processing_errors'],
                'latest_commit_hash': commits[-1]['hash'] if commits else None,
                'processing_stats': self.stats
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            # Log final file sizes
            self._log_file_sizes("final")
            
            self.logger.info("Results saved successfully")
            self.logger.info(f"Commits file: {self.commits_file}")
            self.logger.info(f"Activities file: {self.activities_file}")
            self.logger.info(f"Contributors file: {self.contributors_file}")
            self.logger.info(f"Maintainers file: {self.maintainers_file}")
            self.logger.info(f"State file: {self.state_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
            raise

    def cleanup_repository(self):
        """Clean up the cloned repository to save space"""
        if self.repo_dir.exists():
            self.logger.info("Cleaning up repository directory")
            try:
                shutil.rmtree(self.repo_dir)
                self.logger.info("Repository directory cleaned up")
            except Exception as e:
                self.logger.warning(f"Error cleaning up repository: {e}")

    def smart_cleanup_repository(self, keep_commits: int = 5):
        """
        Smart cleanup: Keep only minimum required for future updates.
        
        This removes all historical data that was already processed while keeping:
        - Last N commits for incremental updates
        - Essential git objects and refs
        - Minimal .git structure for future fetches
        
        :param keep_commits: Number of recent commits to keep (default: 5)
        """
        if not self.repo_dir.exists():
            return
            
        self.logger.info(f"Starting smart cleanup: keeping last {keep_commits} commits")
        
        try:
            # Log size before cleanup
            size_before = self._get_directory_size(self.repo_dir)
            self.logger.info(f"Repository size before cleanup: {self._format_size(size_before)}")
            
            # Step 1: Create a shallow clone with only recent commits
            temp_dir = self.repo_dir.parent / f"{self.repo_name}_temp.git"
            
            # Get the hash of the commit we want to keep from (HEAD~keep_commits)
            try:
                cmd = ['git', '-C', str(self.repo_dir), 'rev-parse', f'HEAD~{keep_commits}']
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                shallow_since_commit = result.stdout.strip()
                self.logger.info(f"Keeping commits since: {shallow_since_commit}")
            except subprocess.CalledProcessError:
                # If we don't have enough commits, keep all
                self.logger.info(f"Repository has fewer than {keep_commits} commits, keeping all")
                return
            
            # Step 2: Create new repository with shallow history
            self.logger.info("Creating shallow repository...")
            cmd = [
                'git', 'clone', '--bare', '--shallow-since', 
                f'{keep_commits} days ago',  # Alternative approach using time
                str(self.repo_dir), str(temp_dir)
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                # Fallback: use depth-based shallow clone
                self.logger.info("Time-based shallow clone failed, using depth-based...")
                cmd = [
                    'git', 'clone', '--bare', '--depth', str(keep_commits),
                    str(self.repo_dir), str(temp_dir)
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Step 3: Replace original with shallow version
            shutil.rmtree(self.repo_dir)
            shutil.move(str(temp_dir), str(self.repo_dir))
            
            # Step 4: Configure for future fetches
            self.logger.info("Configuring repository for future updates...")
            
            # Unshallow the repository to allow future fetches
            try:
                cmd = ['git', '-C', str(self.repo_dir), 'config', 'remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*']
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Set the remote URL for future fetches
                cmd = ['git', '-C', str(self.repo_dir), 'remote', 'set-url', 'origin', self.remote_url]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to configure remote: {e}")
            
            # Step 5: Additional cleanup of unnecessary files
            self._cleanup_git_internals()
            
            # Log size after cleanup
            size_after = self._get_directory_size(self.repo_dir)
            size_saved = size_before - size_after
            reduction_percent = (size_saved / size_before * 100) if size_before > 0 else 0
            
            self.logger.info(f"Repository size after cleanup: {self._format_size(size_after)}")
            self.logger.info(f"Space saved: {self._format_size(size_saved)} ({reduction_percent:.1f}% reduction)")
            self.logger.info("Smart cleanup completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during smart cleanup: {e}")
            # If cleanup fails, fall back to keeping the original repository
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

    def _cleanup_git_internals(self):
        """Clean up unnecessary git internal files to save space"""
        try:
            # Remove reflog (history of ref changes)
            reflog_dir = self.repo_dir / "logs"
            if reflog_dir.exists():
                shutil.rmtree(reflog_dir)
                self.logger.debug("Removed reflog directory")
            
            # Remove hooks (not needed for data repository)
            hooks_dir = self.repo_dir / "hooks"
            if hooks_dir.exists():
                shutil.rmtree(hooks_dir)
                self.logger.debug("Removed hooks directory")
            
            # Clean up loose objects and pack them efficiently
            cmd = ['git', '-C', str(self.repo_dir), 'gc', '--aggressive', '--prune=now']
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.debug("Performed aggressive garbage collection")
            
            # Remove unnecessary config entries
            unnecessary_configs = [
                'core.repositoryformatversion',
                'core.filemode',
                'core.logallrefupdates'
            ]
            
            for config in unnecessary_configs:
                try:
                    cmd = ['git', '-C', str(self.repo_dir), 'config', '--unset', config]
                    subprocess.run(cmd, capture_output=True, text=True)
                except:
                    pass  # Ignore if config doesn't exist
                    
        except Exception as e:
            self.logger.warning(f"Error cleaning git internals: {e}")

    def update_repository(self) -> bool:
        """Fetch new commits from remote for incremental updates"""
        if not self.repo_dir.exists():
            self.logger.warning("Repository doesn't exist, cannot update")
            return False
            
        self.logger.info("Fetching new commits from remote...")
        
        try:
            # Unshallow if needed (for repositories that were cleaned up)
            try:
                cmd = ['git', '-C', str(self.repo_dir), 'fetch', '--unshallow']
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("Repository unshallowed for complete fetch")
            except:
                pass  # Ignore if already unshallow
            
            # Fetch new commits
            cmd = ['git', '-C', str(self.repo_dir), 'fetch', 'origin']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.logger.info("Repository updated successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to update repository: {e}")
            self.logger.error(f"Command output: {e.stderr}")
            return False

    def get_new_commits_since_last_run(self, verbose: bool = False) -> List[Dict]:
        """Get only commits since last processing"""
        if not self.state_file.exists():
            self.logger.info("No previous state found, processing all commits")
            return self.get_commits(verbose=verbose)
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            last_commit = state.get('latest_commit_hash')
            if not last_commit:
                self.logger.info("No previous commit hash found, processing all commits")
                return self.get_commits(verbose=verbose)
            
            self.logger.info(f"Getting commits since last processed: {last_commit}")
            
            # Check if the last commit still exists (might have been cleaned up)
            try:
                cmd = ['git', '-C', str(self.repo_dir), 'cat-file', '-e', last_commit]
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.logger.warning("Last processed commit not found in repository, processing all commits")
                return self.get_commits(verbose=verbose)
            
            # Get commits since last processed
            commit_range = f"{last_commit}..HEAD"
            
            splitter = "--CROWD-END-OF-COMMIT--"
            
            git_log_command = [
                "git",
                "-C",
                str(self.repo_dir),
                "log",
                commit_range,
                f"--pretty=format:%H%n%aI%n%an%n%ae%n%cI%n%cn%n%ce%n%P%n%d%n%B%n{splitter}",
            ]
            
            subprocess.check_output(["git", "-C", str(self.repo_dir), "config", "core.abbrevCommit", "false"])
            
            start_time = time.time()
            try:
                commits_output = (
                    subprocess.check_output(git_log_command).decode("utf-8", errors="replace").strip()
                )
            except Exception as e:
                self.logger.error(f"Failed to get new commits: {e}")
                return []
            
            if not commits_output:
                self.logger.info("No new commits found")
                return []
            
            # Parse commits using same logic as get_commits
            bad_commits = 0
            commits = []
            
            commits_texts = commits_output.split(splitter)
            if verbose and HAS_TQDM:
                commits_iter = tqdm.tqdm(commits_texts, desc="Parsing new commits")
            else:
                commits_iter = commits_texts
            
            for commit_text in commits_iter:
                commit_lines = commit_text.strip().splitlines()
                
                if len(commit_lines) < 8:
                    bad_commits += 1
                    store_bad_commits(commit_text, str(self.repo_dir))
                    continue
                
                commit_hash = commit_lines[0]
                author_datetime = commit_lines[1]
                author_name = commit_lines[2]
                author_email = commit_lines[3]
                
                if author_email is None or author_email.strip() == "":
                    bad_commits += 1
                    store_bad_commits(commit_text, str(self.repo_dir))
                    continue
                
                commit_datetime = commit_lines[4]
                commit_datetime_obj = datetime.datetime.strptime(commit_datetime, "%Y-%m-%dT%H:%M:%S%z")
                if commit_datetime_obj > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1):
                    commit_datetime = author_datetime
                    
                committer_name = commit_lines[5]
                committer_email = commit_lines[6]
                parent_hashes = commit_lines[7].split()
                
                if len(commit_lines) >= 9:
                    ref_names = commit_lines[8].strip()
                else:
                    ref_names = ""
                
                if len(commit_lines) >= 10:
                    commit_message = commit_lines[9:]
                else:
                    commit_message = ""
                
                if not (is_valid_commit_hash(commit_hash) and is_valid_datetime(commit_datetime)):
                    self.logger.error(f"Invalid commit data found: hash={commit_hash}, datetime={commit_datetime}")
                    bad_commits += 1
                    store_bad_commits(commit_text, str(self.repo_dir))
                    continue
                
                is_merge_commit = len(parent_hashes) > 1
                is_main_branch = True
                
                commits.append({
                    "hash": commit_hash,
                    "author_datetime": author_datetime,
                    "author_name": author_name,
                    "author_email": author_email,
                    "committer_datetime": commit_datetime,
                    "committer_name": committer_name,
                    "committer_email": committer_email,
                    "is_main_branch": is_main_branch,
                    "is_merge_commit": is_merge_commit,
                    "message": commit_message,
                })
            
            end_time = time.time()
            self.logger.info(
                f"{len(commits)} new commits extracted in {end_time - start_time:.2f} seconds, {bad_commits} bad commits"
            )
            
            return commits
            
        except Exception as e:
            self.logger.error(f"Error getting new commits: {e}")
            return []

    def process(self, cleanup: bool = True, smart_cleanup: bool = False, update_mode: bool = False, keep_commits: int = 5, verbose: bool = False) -> bool:
        """
        Main processing method with support for incremental updates and smart cleanup.
        
        :param cleanup: If True, completely remove repository after processing
        :param smart_cleanup: If True, keep minimal repository for future updates
        :param update_mode: If True, fetch and process only new commits
        :param keep_commits: Number of recent commits to keep during smart cleanup
        :param verbose: Enable verbose output
        """
        self.logger.info(f"Starting processing for: {self.remote_url}")
        self.logger.info(f"Mode: {'Update' if update_mode else 'Full processing'}")
        self.stats['start_time'] = datetime.datetime.now(timezone.utc).isoformat()
        
        try:
            # Handle update mode
            if update_mode:
                if not self.repo_dir.exists():
                    self.logger.info("Repository doesn't exist for update mode, switching to full processing")
                    update_mode = False
                else:
                    # Update repository and process only new commits
                    if not self.update_repository():
                        return False
                    
                    # Get only new commits since last run
                    new_commits = self.get_new_commits_since_last_run(verbose=verbose)
                    
                    if not new_commits:
                        self.logger.info("No new commits to process")
                        return True
                    
                    # Process new commits with insertions/deletions
                    insertions_deletions = self.get_insertions_deletions_for_commits(new_commits, verbose=verbose)
                    commits_with_changes = self.add_insertions_deletions(new_commits, insertions_deletions)
                    
                    # Prepare activities for new commits
                    self.logger.info("Preparing crowd activities for new commits")
                    activities = prepare_crowd_activities(self.remote_url, commits_with_changes, verbose=verbose)
                    
                    # Update contributors (merge with existing)
                    contributors = self.update_contributors_incremental(commits_with_changes)
                    
                    # Extract maintainers (always get latest)
                    maintainers = self._extract_maintainers()
                    
                    # Save incremental results
                    self.save_incremental_results(commits_with_changes, activities, contributors, maintainers)
                    
                    self.stats['processed_commits'] = len(commits_with_changes)
                    self.stats['contributors_found'] = len(contributors)
                    self.stats['activities_found'] = len(activities)
                    
                    self.logger.info(f"Processed {len(commits_with_changes)} new commits")
                    self.logger.info(f"Generated {len(activities)} new activities")
            
            # Full processing mode (initial run or fallback)
            if not update_mode:
                # Check if already processed (unless forced)
                if self.check_already_processed():
                    return True
                
                # Log initial state
                self._log_file_sizes("initial")
                
                # Clone repository
                if not self.clone_repository():
                    return False
                
                # Process all commits using exact git-integration logic
                commits, activities, contributors = self.process_commits(verbose=verbose)
                
                if not commits:
                    self.logger.error("No commits processed")
                    return False
                
                # Extract maintainers
                maintainers = self._extract_maintainers()
                
                # Save results
                self.save_results(commits, activities, contributors, maintainers)
            
            # Handle cleanup options
            if cleanup:
                self.cleanup_repository()  # Complete removal
            elif smart_cleanup:
                self.smart_cleanup_repository(keep_commits=keep_commits)  # Keep minimal for updates
            # If neither cleanup nor smart_cleanup, keep full repository
            
            self.stats['end_time'] = datetime.datetime.now(timezone.utc).isoformat()
            
            # Log final statistics
            self.log_final_stats()
            
            self.logger.info("Processing completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during processing: {e}")
            return False

    def get_insertions_deletions_for_commits(self, commits: List[Dict], verbose: bool = False) -> Dict[str, Dict]:
        """Get insertions/deletions for specific commits"""
        if not commits:
            return {}
            
        commit_hashes = [commit['hash'] for commit in commits]
        self.logger.info(f"Extracting insertions/deletions for {len(commit_hashes)} commits")
        
        # Create a temporary commit range for these specific commits
        changes = {}
        
        for commit_hash in commit_hashes:
            try:
                cmd = [
                    "git", "-C", str(self.repo_dir), "show",
                    "--pretty=format:", "--numstat", commit_hash
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                lines = result.stdout.strip().split('\n')
                
                insertions = 0
                deletions = 0
                
                for line in lines:
                    if line and '\t' in line:
                        match = re.match(r"^(\d+)\s+(\d+)", line)
                        if match:
                            insertions += int(match.group(1))
                            deletions += int(match.group(2))
                
                changes[commit_hash] = {"insertions": insertions, "deletions": deletions}
                
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to get changes for commit {commit_hash}: {e}")
                changes[commit_hash] = {"insertions": 0, "deletions": 0}
        
        return changes

    def update_contributors_incremental(self, new_commits: List[Dict]) -> Dict:
        """Update contributors with new commits, merging with existing data"""
        # Load existing contributors if available
        contributors = {}
        if self.contributors_file.exists():
            try:
                with open(self.contributors_file, 'r', encoding='utf-8') as f:
                    contributors = json.load(f)
                self.logger.info(f"Loaded {len(contributors)} existing contributors")
            except Exception as e:
                self.logger.warning(f"Failed to load existing contributors: {e}")
        
        # Add new commits to contributors
        for commit in new_commits:
            author_email = commit['author_email']
            committer_email = commit['committer_email']
            
            # Update author
            if author_email not in contributors:
                contributors[author_email] = {
                    'name': commit['author_name'],
                    'email': author_email,
                    'commits_authored': 0,
                    'commits_committed': 0,
                    'first_commit': commit['author_datetime'],
                    'last_commit': commit['author_datetime']
                }
            
            contributors[author_email]['commits_authored'] += 1
            contributors[author_email]['last_commit'] = commit['author_datetime']
            
            # Update committer if different
            if committer_email != author_email:
                if committer_email not in contributors:
                    contributors[committer_email] = {
                        'name': commit['committer_name'],
                        'email': committer_email,
                        'commits_authored': 0,
                        'commits_committed': 0,
                        'first_commit': commit['committer_datetime'],
                        'last_commit': commit['committer_datetime']
                    }
                contributors[committer_email]['commits_committed'] += 1
        
        return contributors

    def save_incremental_results(self, new_commits: List[Dict], new_activities: List[Dict], contributors: Dict, maintainers: Dict):
        """Save incremental results, appending to existing data"""
        self.logger.info("Saving incremental results")
        
        try:
            # Append new commits to existing commits file
            existing_commits = []
            if self.commits_file.exists():
                with open(self.commits_file, 'r', encoding='utf-8') as f:
                    existing_commits = json.load(f)
            
            all_commits = existing_commits + new_commits
            with open(self.commits_file, 'w', encoding='utf-8') as f:
                json.dump(all_commits, f, indent=2, ensure_ascii=False)
            
            # Append new activities to existing activities file
            existing_activities = []
            if self.activities_file.exists():
                with open(self.activities_file, 'r', encoding='utf-8') as f:
                    existing_activities = json.load(f)
            
            all_activities = existing_activities + new_activities
            with open(self.activities_file, 'w', encoding='utf-8') as f:
                json.dump(all_activities, f, indent=2, ensure_ascii=False)
            
            # Save updated contributors (already merged)
            with open(self.contributors_file, 'w', encoding='utf-8') as f:
                json.dump(contributors, f, indent=2, ensure_ascii=False)
            
            # Save updated maintainers
            with open(self.maintainers_file, 'w', encoding='utf-8') as f:
                json.dump(maintainers, f, indent=2, ensure_ascii=False)
            
            # Update processing state
            state = {
                'repository_url': self.remote_url,
                'repository_name': self.repo_name,
                'processing_complete': True,
                'completion_time': datetime.datetime.now(timezone.utc).isoformat(),
                'total_commits': len(all_commits),
                'processed_commits': self.stats['processed_commits'],
                'contributors_found': self.stats['contributors_found'],
                'maintainers_found': self.stats['maintainers_found'],
                'activities_found': len(all_activities),
                'processing_errors': self.stats['processing_errors'],
                'latest_commit_hash': new_commits[-1]['hash'] if new_commits else None,
                'processing_stats': self.stats,
                'last_update': datetime.datetime.now(timezone.utc).isoformat(),
                'incremental_updates': state.get('incremental_updates', 0) + 1 if self.state_file.exists() else 1
            }
            
            # Load existing state to preserve history
            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        existing_state = json.load(f)
                    state['initial_processing_time'] = existing_state.get('completion_time', state['completion_time'])
                    state['incremental_updates'] = existing_state.get('incremental_updates', 0) + 1
                except:
                    pass
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            # Log final file sizes
            self._log_file_sizes("incremental_update")
            
            self.logger.info("Incremental results saved successfully")
            self.logger.info(f"Total commits: {len(all_commits)} (+{len(new_commits)} new)")
            self.logger.info(f"Total activities: {len(all_activities)} (+{len(new_activities)} new)")
            
        except Exception as e:
            self.logger.error(f"Error saving incremental results: {e}")
            raise

    def log_final_stats(self):
        """Log final processing statistics"""
        start_time = datetime.datetime.fromisoformat(self.stats['start_time'])
        end_time = datetime.datetime.fromisoformat(self.stats['end_time'])
        total_time = (end_time - start_time).total_seconds()
        
        self.logger.info("=== FINAL PROCESSING STATISTICS ===")
        self.logger.info(f"Repository: {self.repo_name}")
        self.logger.info(f"Total processing time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
        self.logger.info(f"Total commits: {self.stats['total_commits']}")
        self.logger.info(f"Processed commits: {self.stats['processed_commits']}")
        self.logger.info(f"Contributors found: {self.stats['contributors_found']}")
        self.logger.info(f"Maintainers found: {self.stats['maintainers_found']}")
        self.logger.info(f"Activities generated: {self.stats['activities_found']}")
        self.logger.info(f"Processing errors: {self.stats['processing_errors']}")
        
        if self.stats['total_commits'] > 0:
            rate = self.stats['processed_commits'] / total_time
            self.logger.info(f"Processing rate: {rate:.2f} commits/second")
        
        self.logger.info("=== FILE SIZE SUMMARY ===")
        for stage, sizes in self.stats['file_sizes'].items():
            self.logger.info(f"{stage.upper()}:")
            for name, size in sizes.items():
                self.logger.info(f"  {name}: {self._format_size(size)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Historical Git Repository Processor')
    parser.add_argument('remote_url', help='Remote repository URL to process')
    parser.add_argument('--output-dir', default='historical_output',
                       help='Output directory for results (default: historical_output)')
    
    # Cleanup options (mutually exclusive)
    cleanup_group = parser.add_mutually_exclusive_group()
    cleanup_group.add_argument('--cleanup', action='store_true',
                              help='Completely remove repository after processing (default for first run)')
    cleanup_group.add_argument('--smart-cleanup', action='store_true',
                              help='Keep minimal repository for future updates (recommended)')
    cleanup_group.add_argument('--no-cleanup', action='store_true',
                              help='Keep full repository (uses most space)')
    
    # Processing options
    parser.add_argument('--update', action='store_true',
                       help='Update mode: fetch and process only new commits since last run')
    parser.add_argument('--keep-commits', type=int, default=5,
                       help='Number of recent commits to keep during smart cleanup (default: 5)')
    
    # General options
    parser.add_argument('--force', action='store_true',
                       help='Force reprocessing even if already completed')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output with progress bars')
    
    args = parser.parse_args()
    
    # Create processor
    processor = HistoricalProcessor(args.remote_url, args.output_dir)
    
    # Force reprocessing if requested
    if args.force and processor.state_file.exists():
        processor.state_file.unlink()
        processor.logger.info("Forcing reprocessing - removed existing state file")
    
    # Determine cleanup strategy
    if args.cleanup:
        cleanup = True
        smart_cleanup = False
    elif args.no_cleanup:
        cleanup = False
        smart_cleanup = False
    else:
        # Default behavior: smart cleanup (whether --smart-cleanup specified or not)
        cleanup = False
        smart_cleanup = True
        if not args.smart_cleanup:
            print("💡 Using smart cleanup by default (keeps minimal repo for updates)")
            print("   Use --cleanup to remove completely, --no-cleanup to keep full repo")
    
    # Process repository
    success = processor.process(
        cleanup=cleanup,
        smart_cleanup=smart_cleanup,
        update_mode=args.update,
        keep_commits=args.keep_commits,
        verbose=args.verbose
    )
    
    if success:
        print(f"\n✅ Processing completed successfully!")
        print(f"📁 Results saved in: {processor.output_dir}")
        print(f"📊 Commits: {processor.commits_file}")
        print(f"🎯 Activities: {processor.activities_file}")
        print(f"👥 Contributors: {processor.contributors_file}")
        print(f"🔧 Maintainers: {processor.maintainers_file}")
        print(f"📋 State: {processor.state_file}")
        
        if smart_cleanup:
            print(f"\n🧹 Smart cleanup completed:")
            print(f"   - Kept last {args.keep_commits} commits for future updates")
            print(f"   - Removed historical data already processed")
            print(f"   - Repository ready for incremental updates")
            print(f"\n🔄 For future updates, run:")
            print(f"   python historical_processor.py {args.remote_url} --update")
        elif not cleanup:
            print(f"\n📦 Full repository preserved for future updates")
            print(f"🔄 For future updates, run:")
            print(f"   python historical_processor.py {args.remote_url} --update")
        
        sys.exit(0)
    else:
        print(f"\n❌ Processing failed!")
        sys.exit(1)


if __name__ == '__main__':
    main() 