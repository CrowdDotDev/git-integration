#!/usr/bin/env python3
"""
Incremental Git Repository Processor - Database-Driven Approach
Processes git repositories incrementally from a given commit hash to HEAD.
Uses minimal shallow cloning for maximum efficiency.
"""

import os
import sys
import json
import shutil
import logging
import argparse
import tempfile
import subprocess
import psutil
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configure logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'incremental_processor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

class IncrementalProcessor:
    def __init__(self, repo_url: str, start_commit: str):
        self.repo_url = repo_url
        self.start_commit = start_commit
        self.repo_name = self._extract_repo_name(repo_url)
        self.temp_dir = None
        self.repo_path = None
        self.target_branch = None
        self.current_process = psutil.Process()
        self.metrics = {
            'start_time': datetime.now(),
            'storage_sizes': {},
            'processing_times': {},
            'commit_counts': {},
            'maintainer_files_found': [],
            'maintainer_stats': {
                'total_files_checked': 0,
                'files_found': 0,
                'maintainers_by_type': {},
                'maintainers_by_file': {}
            },
            'error_stats': {
                'total_errors': 0,
                'error_types': {},
                'recovery_attempts': 0,
                'recovery_successes': 0
            },
            'resource_usage': {
                'memory_peaks': [],
                'cpu_peaks': [],
                'network_usage': {
                    'bytes_sent': 0,
                    'bytes_received': 0
                }
            },
            'errors': []
        }
        self._start_network_monitoring()
        
    def _start_network_monitoring(self):
        """Start monitoring network usage."""
        self.initial_net_io = psutil.net_io_counters()
    
    def _update_network_metrics(self):
        """Update network usage metrics."""
        current_net_io = psutil.net_io_counters()
        self.metrics['resource_usage']['network_usage']['bytes_sent'] = current_net_io.bytes_sent - self.initial_net_io.bytes_sent
        self.metrics['resource_usage']['network_usage']['bytes_received'] = current_net_io.bytes_recv - self.initial_net_io.bytes_recv
    
    def _update_resource_metrics(self):
        """Update memory and CPU usage metrics."""
        memory_info = self.current_process.memory_info()
        cpu_percent = self.current_process.cpu_percent()
        
        self.metrics['resource_usage']['memory_peaks'].append({
            'timestamp': datetime.now().isoformat(),
            'rss': memory_info.rss,
            'vms': memory_info.vms
        })
        
        self.metrics['resource_usage']['cpu_peaks'].append({
            'timestamp': datetime.now().isoformat(),
            'percent': cpu_percent
        })
    
    def _record_error(self, error_type: str, error_msg: str, recovery_attempted: bool = False, recovery_success: bool = False):
        """Record error statistics."""
        self.metrics['error_stats']['total_errors'] += 1
        self.metrics['error_stats']['error_types'][error_type] = self.metrics['error_stats']['error_types'].get(error_type, 0) + 1
        
        if recovery_attempted:
            self.metrics['error_stats']['recovery_attempts'] += 1
            if recovery_success:
                self.metrics['error_stats']['recovery_successes'] += 1
        
        self.metrics['errors'].append({
            'type': error_type,
            'message': error_msg,
            'timestamp': datetime.now().isoformat(),
            'recovery_attempted': recovery_attempted,
            'recovery_success': recovery_success
        })

    def _extract_repo_name(self, url: str) -> str:
        """Extract repository name from URL."""
        return url.rstrip('/').split('/')[-1].replace('.git', '')
    
    def _run_git_command(self, cmd: List[str], cwd: str = None) -> Tuple[bool, str]:
        """Run git command and return success status and output."""
        try:
            self._update_resource_metrics()
            result = subprocess.run(
                cmd, 
                cwd=cwd or self.repo_path,
                capture_output=True, 
                text=True, 
                check=True
            )
            self._update_network_metrics()
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self._record_error('git_command', e.stderr)
            logger.error(f"Git command failed: {' '.join(cmd)}")
            logger.error(f"Error: {e.stderr}")
            return False, e.stderr
    
    def _create_minimal_clone(self) -> bool:
        """Create minimal shallow clone from start_commit to HEAD."""
        logger.info(f"Creating minimal clone from {self.start_commit} to HEAD")
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix=f"git_incremental_{self.repo_name}_")
        self.repo_path = os.path.join(self.temp_dir, self.repo_name)
        
        try:
            # Create the repository directory
            os.makedirs(self.repo_path, exist_ok=True)
            
            # Initialize bare repository (git init --bare needs to run in the target directory)
            success, _ = self._run_git_command(['git', 'init', '--bare'], cwd=self.repo_path)
            if not success:
                return False
            
            # Add remote (now we can use self.repo_path as cwd)
            success, _ = self._run_git_command(['git', 'remote', 'add', 'origin', self.repo_url])
            if not success:
                return False
            
            # Ultra-minimal strategy: Start with just the latest commit
            logger.info("Fetching only the latest commit (depth=1)...")
            start_time = datetime.now()
            success, _ = self._run_git_command(['git', 'fetch', '--depth=1', 'origin', 'HEAD'])
            fetch_time = (datetime.now() - start_time).total_seconds()
            
            # Record initial metrics
            self.metrics['storage_sizes']['initial'] = self._get_directory_size(self.repo_path)
            self.metrics['processing_times']['initial_fetch'] = fetch_time
            
            if not success:
                # Try with main/master if HEAD fails
                logger.info("HEAD fetch failed, trying main...")
                success, _ = self._run_git_command(['git', 'fetch', '--depth=1', 'origin', 'main'])
                if not success:
                    logger.info("main fetch failed, trying master...")
                    success, _ = self._run_git_command(['git', 'fetch', '--depth=1', 'origin', 'master'])
                    if not success:
                        logger.error("Could not fetch any branch with depth=1")
                        return False
            
            # Check repository size after minimal fetch
            repo_size = self._get_directory_size(self.repo_path)
            logger.info(f"Repository size after minimal fetch: {repo_size / (1024*1024):.1f} MB")
            
            # Now check if we have the start commit
            success, _ = self._run_git_command(['git', 'cat-file', '-e', self.start_commit])
            
            if not success:
                logger.info(f"Start commit {self.start_commit[:8]} not found, deepening history...")
                
                # Try deepening in small increments with better progress feedback
                depths = [10, 25, 50, 100, 250, 500, 1000, 2000]
                
                for i, depth in enumerate(depths, 1):
                    logger.info(f"🔍 Deepening attempt {i}/{len(depths)}: fetching {depth} commits...")
                    start_time = datetime.now()
                    
                    success, output = self._run_git_command([
                        'git', 'fetch', f'--depth={depth}', 'origin'
                    ])
                    
                    fetch_time = (datetime.now() - start_time).total_seconds()
                    
                    if success:
                        # Check repository size after this fetch
                        current_size = self._get_directory_size(self.repo_path)
                        logger.info(f"✅ Fetch completed in {fetch_time:.1f}s - Repository size: {current_size / (1024*1024):.1f} MB")
                        
                        # Record metrics for this depth
                        self.metrics['storage_sizes'][f'depth_{depth}'] = current_size
                        self.metrics['processing_times'][f'fetch_depth_{depth}'] = fetch_time
                        
                        # Check if we now have the start commit
                        logger.info(f"🔎 Checking if start commit {self.start_commit[:8]} is now available...")
                        success, _ = self._run_git_command(['git', 'cat-file', '-e', self.start_commit])
                        if success:
                            logger.info(f"🎉 Found start commit at depth {depth}!")
                            break
                        else:
                            logger.info(f"❌ Start commit not found at depth {depth}, trying deeper...")
                    else:
                        logger.warning(f"⚠️  Fetch failed at depth {depth}: {output}")
                    
                    # Check size to avoid runaway growth
                    if current_size > 100 * 1024 * 1024:  # 100MB limit
                        logger.warning(f"🛑 Repository size exceeded 100MB, stopping deepening")
                        break
                        
                    # Estimate remaining time based on current progress
                    if i < len(depths):
                        next_depth = depths[i]
                        estimated_time = fetch_time * (next_depth / depth)
                        logger.info(f"⏱️  Next: depth {next_depth} (estimated {estimated_time:.1f}s)")
                else:
                    # If we still don't have the commit after all attempts
                    logger.warning(f"❌ Could not find start commit {self.start_commit[:8]} with limited depth")
                    logger.info("🔄 Attempting unshallow as last resort...")
                    start_time = datetime.now()
                    
                    success, _ = self._run_git_command(['git', 'fetch', '--unshallow', 'origin'])
                    unshallow_time = (datetime.now() - start_time).total_seconds()
                    
                    if success:
                        final_size = self._get_directory_size(self.repo_path)
                        logger.info(f"✅ Unshallow completed in {unshallow_time:.1f}s - Final size: {final_size / (1024*1024):.1f} MB")
                        
                        # Record unshallow metrics
                        self.metrics['storage_sizes']['unshallow'] = final_size
                        self.metrics['processing_times']['unshallow'] = unshallow_time
                    else:
                        logger.error("❌ Unshallow failed, cannot proceed")
                        return False
            else:
                logger.info(f"✅ Start commit {self.start_commit[:8]} found in minimal fetch!")
            
            # Set up the default branch reference
            success, default_branch = self._run_git_command([
                'git', 'symbolic-ref', 'refs/remotes/origin/HEAD'
            ])
            if not success:
                # Try to determine default branch from fetched refs
                success, refs = self._run_git_command(['git', 'branch', '-r'])
                if success and 'origin/main' in refs:
                    default_branch = 'main'
                    self._run_git_command(['git', 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main'])
                elif success and 'origin/master' in refs:
                    default_branch = 'master'
                    self._run_git_command(['git', 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/master'])
                else:
                    default_branch = 'main'  # fallback
            else:
                default_branch = default_branch.split('/')[-1]
            
            logger.info(f"Using default branch: {default_branch}")
            
            # Final repository size
            final_size = self._get_directory_size(self.repo_path)
            logger.info(f"Final repository size: {final_size / (1024*1024):.1f} MB")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create minimal clone: {e}")
            self.metrics['errors'].append({
                'operation': 'create_minimal_clone',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return False
    
    def _get_directory_size(self, path: str) -> int:
        """Get total size of directory in bytes."""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total += os.path.getsize(filepath)
        except OSError:
            pass
        return total
    
    def _get_commits_to_process(self) -> List[str]:
        """Get list of commit hashes from start_commit to HEAD."""
        logger.info("Getting commits to process...")
        
        # First, try to find the latest commit from fetched branches
        success, refs = self._run_git_command(['git', 'branch', '-r'])
        if not success:
            logger.error("Failed to get remote branches")
            return []
        
        # Determine the target branch (prefer main, then master, then first available)
        target_ref = None
        if 'origin/main' in refs:
            target_ref = 'origin/main'
        elif 'origin/master' in refs:
            target_ref = 'origin/master'
        else:
            # Get the first remote branch
            remote_branches = [line.strip() for line in refs.split('\n') if line.strip() and 'origin/' in line]
            if remote_branches:
                target_ref = remote_branches[0].strip()
        
        if not target_ref:
            logger.error("No remote branches found")
            return []
        
        # Store the target branch for use in maintainer extraction
        self.target_branch = target_ref
        logger.info(f"Using target branch: {target_ref}")
        
        # Get commits from start_commit (exclusive) to target branch
        start_time = datetime.now()
        success, output = self._run_git_command([
            'git', 'rev-list', f'{self.start_commit}..{target_ref}', '--reverse'
        ])
        rev_list_time = (datetime.now() - start_time).total_seconds()
        
        if not success:
            logger.error(f"Failed to get commit list from {self.start_commit[:8]} to {target_ref}")
            # Try alternative: check if start_commit exists at all
            success, _ = self._run_git_command(['git', 'cat-file', '-e', self.start_commit])
            if not success:
                logger.error(f"Start commit {self.start_commit[:8]} not found in repository")
                return []
            else:
                logger.error("Start commit exists but range query failed")
                return []
        
        commits = [line.strip() for line in output.split('\n') if line.strip()]
        logger.info(f"Found {len(commits)} commits to process")
        
        # Record metrics
        self.metrics['commit_counts']['total'] = len(commits)
        self.metrics['processing_times']['rev_list'] = rev_list_time
        
        return commits
    
    def _process_commit(self, commit_hash: str) -> Optional[Dict]:
        """Process a single commit and extract data."""
        try:
            start_time = datetime.now()
            
            # Get commit info
            success, commit_info = self._run_git_command([
                'git', 'show', '--format=%H|%an|%ae|%ad|%s', '--name-only', commit_hash
            ])
            
            if not success:
                logger.error(f"Failed to get commit info for {commit_hash}")
                return None
            
            lines = commit_info.split('\n')
            if not lines:
                return None
            
            # Parse commit metadata
            metadata = lines[0].split('|')
            if len(metadata) < 5:
                logger.warning(f"Invalid commit metadata for {commit_hash}")
                return None
            
            commit_data = {
                'hash': metadata[0],
                'author_name': metadata[1],
                'author_email': metadata[2],
                'date': metadata[3],
                'message': metadata[4],
                'files': []
            }
            
            # Get file changes
            files = [line.strip() for line in lines[1:] if line.strip()]
            commit_data['files'] = files
            
            # Get insertion/deletion stats
            success, stats = self._run_git_command([
                'git', 'show', '--format=', '--numstat', commit_hash
            ])
            
            if success:
                insertions = 0
                deletions = 0
                for line in stats.split('\n'):
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2 and parts[0] != '-' and parts[1] != '-':
                            try:
                                insertions += int(parts[0])
                                deletions += int(parts[1])
                            except ValueError:
                                pass
                
                commit_data['insertions'] = insertions
                commit_data['deletions'] = deletions
            
            # Extract activities from commit message
            commit_data['activities'] = self._extract_activities(commit_data['message'])
            
            # Record processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            self.metrics['processing_times'][f'commit_{commit_hash[:8]}'] = processing_time
            
            return commit_data
            
        except Exception as e:
            logger.error(f"Error processing commit {commit_hash}: {e}")
            self.metrics['errors'].append({
                'commit': commit_hash,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None
    
    def _extract_activities(self, message: str) -> List[str]:
        """Extract activities from commit message (simplified version)."""
        activities = []
        message_lower = message.lower()
        
        # Simple activity detection (can be enhanced)
        activity_keywords = {
            'fix': ['fix', 'fixes', 'fixed', 'bug', 'issue'],
            'feature': ['add', 'adds', 'added', 'feature', 'implement'],
            'update': ['update', 'updates', 'updated', 'modify', 'change'],
            'remove': ['remove', 'removes', 'removed', 'delete', 'drop'],
            'refactor': ['refactor', 'refactors', 'refactored', 'cleanup'],
            'docs': ['doc', 'docs', 'documentation', 'readme'],
            'test': ['test', 'tests', 'testing', 'spec']
        }
        
        for activity, keywords in activity_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                activities.append(activity)
        
        return activities if activities else ['commit']
    
    def _extract_maintainers(self) -> List[Dict]:
        """Extract maintainer information from latest version."""
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
        self.metrics['maintainer_stats']['total_files_checked'] = len(maintainer_files)
        
        # Determine the default branch (main or master)
        success, refs = self._run_git_command(['git', 'branch', '-r'])
        if not success:
            logger.error("Failed to get remote branches for maintainer extraction")
            return maintainers
        
        # Find the default branch
        default_branch_ref = None
        if 'origin/main' in refs:
            default_branch_ref = 'origin/main'
        elif 'origin/master' in refs:
            default_branch_ref = 'origin/master'
        else:
            logger.error("Could not find main or master branch for maintainer extraction")
            return maintainers
        
        logger.info(f"Using default branch {default_branch_ref} for maintainer extraction")
        
        # Try each maintainer file in order
        for filename in maintainer_files:
            success, content = self._run_git_command([
                'git', 'show', f'{default_branch_ref}:{filename}'
            ])
            
            if success and content:
                logger.info(f"Found maintainer file: {filename}")
                self.metrics['maintainer_stats']['files_found'] += 1
                self.metrics['maintainer_files_found'].append(filename)
                
                file_maintainers = self._parse_maintainer_file(filename, content)
                maintainers.extend(file_maintainers)
                
                # Update maintainer statistics
                for maintainer in file_maintainers:
                    maintainer_type = maintainer['type']
                    self.metrics['maintainer_stats']['maintainers_by_type'][maintainer_type] = \
                        self.metrics['maintainer_stats']['maintainers_by_type'].get(maintainer_type, 0) + 1
                    
                    self.metrics['maintainer_stats']['maintainers_by_file'][filename] = \
                        self.metrics['maintainer_stats']['maintainers_by_file'].get(filename, 0) + 1
                
                break
        
        return maintainers
    
    def _parse_maintainer_file(self, filename: str, content: str) -> List[Dict]:
        """Parse maintainer file using regex patterns."""
        maintainers = []
        import re
        
        for line_num, line in enumerate(content.split('\n'), 1):
            original_line = line
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Different parsing strategies based on file type
            if filename.upper() in ['CODEOWNERS', '.GITHUB/CODEOWNERS', 'CODEOWNERS.MD']:
                # CODEOWNERS format: path @username @username2 email@domain.com
                # Extract GitHub usernames (@username) and email addresses
                
                # Find GitHub usernames (@ followed by alphanumeric/underscore/hyphen)
                github_users = re.findall(r'@([a-zA-Z0-9_-]+)(?!\.[a-zA-Z])', line)
                for username in github_users:
                    maintainers.append({
                        'github_username': username,
                        'name': username,  # Use username as name fallback
                        'title': 'Code Owner',
                        'normalized_title': 'maintainer',
                        'type': 'github_username',
                        'value': username,
                        'file': filename,
                        'line': original_line,
                        'line_number': line_num
                    })
                
                # Also extract email addresses
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                for email in emails:
                    # Extract name from email if possible
                    name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                    maintainers.append({
                        'github_username': 'unknown',
                        'name': name,
                        'title': 'Code Owner',
                        'normalized_title': 'maintainer',
                        'type': 'email',
                        'value': email,
                        'file': filename,
                        'line': original_line,
                        'line_number': line_num
                    })
                    
            elif filename.upper() == 'OWNERS':
                # OWNERS format can vary, but often contains:
                # - approvers: [username1, username2]
                # - reviewers: [username1, username2]
                # - Simple usernames on lines
                
                # Check if this line defines a role
                role = 'Maintainer'  # default
                if 'approver' in line.lower():
                    role = 'Approver'
                elif 'reviewer' in line.lower():
                    role = 'Reviewer'
                elif 'emeritus' in line.lower():
                    role = 'Emeritus'
                
                # Extract usernames from YAML-like lists
                yaml_users = re.findall(r'[-\s]*([a-zA-Z0-9_-]+)(?:\s|$)', line)
                for username in yaml_users:
                    # Skip common YAML keywords
                    if username.lower() not in ['approvers', 'reviewers', 'emeritus_approvers', 'labels', 'emeritus']:
                        maintainers.append({
                            'github_username': username,
                            'name': username,  # Use username as name fallback
                            'title': role,
                            'normalized_title': 'maintainer' if role != 'Reviewer' else 'contributor',
                            'type': 'username',
                            'value': username,
                            'file': filename,
                            'line': original_line,
                            'line_number': line_num
                        })
                        
            else:
                # Traditional maintainer files - look for emails and names
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                for email in emails:
                    # Extract name from email if possible
                    name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                    maintainers.append({
                        'github_username': 'unknown',
                        'name': name,
                        'title': 'Maintainer',
                        'normalized_title': 'maintainer',
                        'type': 'email',
                        'value': email,
                        'file': filename,
                        'line': original_line,
                        'line_number': line_num
                    })
                
                # Also extract GitHub usernames if present
                github_users = re.findall(r'@([a-zA-Z0-9_-]+)', line)
                for username in github_users:
                    maintainers.append({
                        'github_username': username,
                        'name': username,  # Use username as name fallback
                        'title': 'Maintainer',
                        'normalized_title': 'maintainer',
                        'type': 'github_username',
                        'value': username,
                        'file': filename,
                        'line': original_line,
                        'line_number': line_num
                    })
        
        return maintainers
    
    def process(self) -> Dict:
        """Main processing function."""
        logger.info(f"Starting incremental processing for {self.repo_name}")
        logger.info(f"Repository: {self.repo_url}")
        logger.info(f"Start commit: {self.start_commit}")
        
        start_time = datetime.now()
        
        try:
            # Create minimal clone
            if not self._create_minimal_clone():
                raise Exception("Failed to create minimal clone")
            
            # Get commits to process
            commits_to_process = self._get_commits_to_process()
            if not commits_to_process:
                logger.warning("No new commits to process")
                return {
                    'repo_name': self.repo_name,
                    'repo_url': self.repo_url,
                    'start_commit': self.start_commit,
                    'commits': [],
                    'maintainers': [],
                    'processing_time': 0,
                    'status': 'no_new_commits',
                    'metrics': self.metrics
                }
            
            # Process commits
            processed_commits = []
            for i, commit_hash in enumerate(commits_to_process, 1):
                logger.info(f"Processing commit {i}/{len(commits_to_process)}: {commit_hash[:8]}")
                
                commit_data = self._process_commit(commit_hash)
                if commit_data:
                    processed_commits.append(commit_data)
                
                if i % 100 == 0:
                    logger.info(f"Processed {i} commits...")
            
            # Extract maintainers
            maintainers = self._extract_maintainers()
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Update final metrics
            self.metrics['processing_times']['total'] = processing_time
            self.metrics['commit_counts']['processed'] = len(processed_commits)
            self.metrics['maintainer_counts'] = len(maintainers)
            
            # Calculate error rates
            total_operations = (
                self.metrics['commit_counts']['total'] +
                self.metrics['maintainer_stats']['total_files_checked'] +
                len(self.metrics['processing_times'])
            )
            self.metrics['error_stats']['error_rate'] = (
                self.metrics['error_stats']['total_errors'] / total_operations
                if total_operations > 0 else 0
            )
            
            # Calculate recovery success rate
            self.metrics['error_stats']['recovery_success_rate'] = (
                self.metrics['error_stats']['recovery_successes'] / self.metrics['error_stats']['recovery_attempts']
                if self.metrics['error_stats']['recovery_attempts'] > 0 else 0
            )
            
            # Calculate average resource usage
            if self.metrics['resource_usage']['memory_peaks']:
                self.metrics['resource_usage']['average_memory'] = sum(
                    peak['rss'] for peak in self.metrics['resource_usage']['memory_peaks']
                ) / len(self.metrics['resource_usage']['memory_peaks'])
            
            if self.metrics['resource_usage']['cpu_peaks']:
                self.metrics['resource_usage']['average_cpu'] = sum(
                    peak['percent'] for peak in self.metrics['resource_usage']['cpu_peaks']
                ) / len(self.metrics['resource_usage']['cpu_peaks'])
            
            result = {
                'repo_name': self.repo_name,
                'repo_url': self.repo_url,
                'start_commit': self.start_commit,
                'latest_commit': commits_to_process[-1] if commits_to_process else self.start_commit,
                'commits': processed_commits,
                'maintainers': maintainers,
                'processing_time': processing_time,
                'status': 'success',
                'metrics': self.metrics
            }
            
            logger.info(f"Processing completed successfully!")
            logger.info(f"Processed {len(processed_commits)} commits in {processing_time:.1f} seconds")
            logger.info(f"Found {len(maintainers)} maintainer entries")
            logger.info(f"Error rate: {self.metrics['error_stats']['error_rate']:.2%}")
            logger.info(f"Recovery success rate: {self.metrics['error_stats']['recovery_success_rate']:.2%}")
            logger.info(f"Average memory usage: {self.metrics['resource_usage']['average_memory'] / (1024*1024):.1f} MB")
            logger.info(f"Average CPU usage: {self.metrics['resource_usage']['average_cpu']:.1f}%")
            logger.info(f"Network usage: {self.metrics['resource_usage']['network_usage']['bytes_received'] / (1024*1024):.1f} MB received")
            
            return result
            
        except Exception as e:
            self._record_error('process', str(e))
            logger.error(f"Processing failed: {e}")
            return {
                'repo_name': self.repo_name,
                'repo_url': self.repo_url,
                'start_commit': self.start_commit,
                'error': str(e),
                'status': 'error',
                'metrics': self.metrics
            }
        
        finally:
            # Cleanup
            if self.temp_dir and os.path.exists(self.temp_dir):
                logger.info("Cleaning up temporary directory...")
                shutil.rmtree(self.temp_dir)

def main():
    parser = argparse.ArgumentParser(description='Incremental Git Repository Processor')
    parser.add_argument('repo_url', help='Git repository URL')
    parser.add_argument('commit_hash', help='Starting commit hash (exclusive)')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--metrics', '-m', help='Output metrics JSON file path')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.repo_url:
        logger.error("Repository URL is required")
        sys.exit(1)
    
    if not args.commit_hash:
        logger.error("Commit hash is required")
        sys.exit(1)
    
    # Process repository
    processor = IncrementalProcessor(args.repo_url, args.commit_hash)
    result = processor.process()
    
    # Save results
    if args.output:
        output_file = args.output
    else:
        output_file = f"{result['repo_name']}_incremental_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Results saved to: {output_file}")
    except Exception as e:
        logger.error(f"Failed to save results: {e}")
    
    # Save metrics separately if requested
    if args.metrics:
        try:
            with open(args.metrics, 'w') as f:
                json.dump(result['metrics'], f, indent=2, default=str)
            logger.info(f"Metrics saved to: {args.metrics}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    # Print summary
    if result['status'] == 'success':
        print(f"\n✅ Processing completed successfully!")
        print(f"📊 Processed {len(result['commits'])} commits")
        print(f"👥 Found {len(result['maintainers'])} maintainer entries")
        print(f"⏱️  Processing time: {result['processing_time']:.1f} seconds")
        print(f"💾 Results saved to: {output_file}")
        if args.metrics:
            print(f"📈 Metrics saved to: {args.metrics}")
    elif result['status'] == 'no_new_commits':
        print(f"\nℹ️  No new commits to process")
    else:
        print(f"\n❌ Processing failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == '__main__':
    main() 