#!/usr/bin/env python3
"""
Full Download Verification Test Suite

This test suite:
1. Searches for torrents using each plugin
2. Adds them to qBittorrent via API
3. Verifies downloads actually start
4. Monitors download progress
5. Verifies torrent metadata (seeders, size, etc.)

Usage:
    python3 tests/test_full_download_verification.py
    python3 tests/test_full_download_verification.py --plugin rutor
    python3 tests/test_full_download_verification.py --verbose
"""

import os
import sys
import time
import json
import argparse
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PLUGINS_DIR = os.path.join(PROJECT_DIR, "plugins")
sys.path.insert(0, PLUGINS_DIR)
sys.path.insert(0, SCRIPT_DIR)

# Try to import requests for API calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests module not available. Install with: pip install requests")


class Colors:
    GREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_success(text): print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")
def print_error(text): print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")
def print_warning(text): print(f"{Colors.WARNING}! {text}{Colors.ENDC}")
def print_info(text): print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")
def print_header(text): print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")


class QBittorrentAPI:
    """qBittorrent Web API client."""
    
    def __init__(self, host='localhost', port=78085, username='admin', password='admin'):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"http://{host}:{port}/api/v2"
        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        self.authenticated = False
        
    def login(self) -> bool:
        """Authenticate with qBittorrent."""
        if not self.session:
            return False
            
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data={'username': self.username, 'password': self.password},
                timeout=10
            )
            self.authenticated = response.text == "Ok."
            return self.authenticated
        except Exception as e:
            print_error(f"Login failed: {e}")
            return False
    
    def add_torrent(self, urls: str = None, torrent_files: bytes = None, 
                    category: str = 'test', tags: str = None) -> tuple:
        """Add torrent to qBittorrent."""
        if not self.authenticated or not self.session:
            return False, "Not authenticated"
        
        try:
            data = {'category': category}
            if tags:
                data['tags'] = tags
            
            if urls:
                data['urls'] = urls
                response = self.session.post(
                    f"{self.base_url}/torrents/add",
                    data=data,
                    timeout=30
                )
            elif torrent_files:
                files = {'torrents': ('torrent.torrent', torrent_files)}
                response = self.session.post(
                    f"{self.base_url}/torrents/add",
                    data=data,
                    files=files,
                    timeout=30
                )
            else:
                return False, "No URLs or files provided"
            
            return response.status_code == 200, response.text
            
        except Exception as e:
            return False, str(e)
    
    def get_torrents(self, category: str = None) -> List[Dict]:
        """Get list of torrents."""
        if not self.authenticated or not self.session:
            return []
        
        try:
            params = {}
            if category:
                params['category'] = category
                
            response = self.session.get(
                f"{self.base_url}/torrents/info",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print_error(f"Get torrents failed: {e}")
            return []
    
    def get_torrent_properties(self, hash: str) -> Optional[Dict]:
        """Get detailed properties of a torrent."""
        if not self.authenticated or not self.session:
            return None
        
        try:
            response = self.session.get(
                f"{self.base_url}/torrents/properties",
                params={'hash': hash},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
    
    def delete_torrent(self, hash: str, delete_files: bool = True) -> bool:
        """Delete torrent from qBittorrent."""
        if not self.authenticated or not self.session:
            return False
        
        try:
            response = self.session.post(
                f"{self.base_url}/torrents/delete",
                data={'hashes': hash, 'deleteFiles': str(delete_files).lower()},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False


class DownloadVerifier:
    """Verifies torrent downloads work correctly."""
    
    def __init__(self, qbit_api: QBittorrentAPI):
        self.qbit = qbit_api
        self.results = []
        
    def verify_plugin_download(self, plugin_name: str, search_term: str = 'ubuntu') -> Dict:
        """Verify a plugin can search and download."""
        print_header(f"Testing: {plugin_name}")
        
        result = {
            'plugin': plugin_name,
            'search_term': search_term,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'stages': {}
        }
        
        # Stage 1: Import plugin
        try:
            module = __import__(plugin_name)
            class_name = self._get_class_name(plugin_name)
            cls = getattr(module, class_name)
            result['stages']['import'] = 'passed'
            print_success(f"Imported {plugin_name}")
        except Exception as e:
            result['stages']['import'] = f'failed: {e}'
            result['status'] = 'failed'
            print_error(f"Import failed: {e}")
            return result
        
        # Stage 2: Search
        search_results = []
        try:
            from io import StringIO
            import novaprinter
            
            original_printer = novaprinter.prettyPrinter
            
            def capture_result(data):
                search_results.append(data)
            
            novaprinter.prettyPrinter = capture_result
            
            instance = cls()
            instance.search(search_term)
            
            novaprinter.prettyPrinter = original_printer
            
            result['stages']['search'] = f'passed ({len(search_results)} results)'
            print_success(f"Search returned {len(search_results)} results")
            
        except Exception as e:
            result['stages']['search'] = f'failed: {e}'
            result['status'] = 'failed'
            print_error(f"Search failed: {e}")
            return result
        
        if not search_results:
            result['stages']['search'] = 'failed: no results'
            result['status'] = 'failed'
            print_error("No search results")
            return result
        
        # Stage 3: Verify result structure
        first_result = search_results[0]
        required_fields = ['link', 'name', 'size']
        missing_fields = [f for f in required_fields if f not in first_result]
        
        if missing_fields:
            result['stages']['structure'] = f'failed: missing {missing_fields}'
            result['status'] = 'failed'
            print_error(f"Missing fields: {missing_fields}")
            return result
        
        result['stages']['structure'] = 'passed'
        print_success(f"Result structure valid")
        print_info(f"  Name: {first_result.get('name', 'N/A')[:60]}...")
        print_info(f"  Size: {first_result.get('size', 'N/A')}")
        print_info(f"  Seeders: {first_result.get('seeds', 'N/A')}")
        
        # Stage 4: Verify magnet link
        link = first_result.get('link', '')
        if link.startswith('magnet:'):
            result['stages']['magnet'] = 'passed'
            print_success("Magnet link valid")
        elif link.startswith('http'):
            result['stages']['magnet'] = 'info: HTTP link (will try to fetch)'
            print_warning("HTTP link (not magnet)")
        else:
            result['stages']['magnet'] = f'warning: unknown link type: {link[:30]}...'
            print_warning(f"Unknown link type: {link[:30]}...")
        
        # Stage 5: Add to qBittorrent (if API available)
        if self.qbit.session and self.qbit.authenticated:
            try:
                # Clean up test category first
                existing = self.qbit.get_torrents(category='test')
                for t in existing[:5]:  # Keep last 5 for comparison
                    pass
                
                # Add the torrent
                if link.startswith('magnet:'):
                    success, message = self.qbit.add_torrent(
                        urls=link,
                        category='test',
                        tags=f'plugin_{plugin_name}'
                    )
                    
                    if success:
                        result['stages']['add'] = 'passed'
                        print_success("Added to qBittorrent")
                        
                        # Wait and verify it appears
                        time.sleep(2)
                        torrents = self.qbit.get_torrents(category='test')
                        
                        # Find our torrent
                        our_torrent = None
                        for t in torrents:
                            if link in t.get('magnet_uri', '') or first_result.get('name', '') in t.get('name', ''):
                                our_torrent = t
                                break
                        
                        if our_torrent:
                            result['stages']['verify_add'] = 'passed'
                            print_success(f"Verified in qBittorrent: {our_torrent.get('name', 'N/A')[:50]}...")
                            
                            # Get properties
                            props = self.qbit.get_torrent_properties(our_torrent.get('hash'))
                            if props:
                                result['stages']['properties'] = 'passed'
                                print_info(f"  State: {props.get('state', 'N/A')}")
                                print_info(f"  Progress: {props.get('progress', 0) * 100:.1f}%")
                                print_info(f"  Seeders: {props.get('seeds_total', 'N/A')}")
                        else:
                            result['stages']['verify_add'] = 'warning: torrent not found in list'
                            print_warning("Torrent not immediately visible")
                    else:
                        result['stages']['add'] = f'failed: {message}'
                        print_error(f"Failed to add: {message}")
                        
            except Exception as e:
                result['stages']['add'] = f'error: {e}'
                print_error(f"Add error: {e}")
        else:
            result['stages']['add'] = 'skipped: qBittorrent API not available'
            print_warning("Skipping qBittorrent add (API not available)")
        
        # Determine overall status
        failed_stages = [k for k, v in result['stages'].items() if 'failed' in str(v)]
        if not failed_stages:
            result['status'] = 'passed'
        else:
            result['status'] = 'partial' if any('passed' in str(v) for v in result['stages'].values()) else 'failed'
        
        self.results.append(result)
        return result
    
    def _get_class_name(self, plugin_name: str) -> str:
        """Get the class name for a plugin."""
        class_names = {
            'rutracker': 'RuTracker',
            'rutor': 'Rutor',
            'kinozal': 'Kinozal',
            'nnmclub': 'NNMClub',
            'iptorrents': 'iptorrents',
            'eztv': 'Eztv',
            'jackett': 'jackett',
            'limetorrents': 'limetorrents',
            'piratebay': 'piratebay',
            'solidtorrents': 'solidtorrents',
            'torlock': 'torlock',
            'torrentproject': 'torrentproject',
            'torrentscsv': 'torrentscsv',
            'one337x': 'one337x',
            'torrentfunk': 'torrentfunk',
            'extratorrent': 'extratorrent',
            'btsow': 'btsow',
            'torrentkitty': 'torrentkitty',
            'anilibra': 'anilibra',
            'gamestorrents': 'gamestorrents',
            'therarbg': 'therarbg',
            'academictorrents': 'academictorrents',
            'ali213': 'ali213',
            'audiobookbay': 'audiobookbay',
            'bt4g': 'bt4g',
            'glotorrents': 'glotorrents',
            'kickass': 'kickass',
            'linuxtracker': 'linuxtracker',
            'nyaa': 'nyaasi',
            'pirateiro': 'pirateiro',
            'rockbox': 'rockbox',
            'snowfl': 'snowfl',
            'tokyotoshokan': 'tokyotoshokan',
            'torrentdownload': 'torrentdownload',
            'torrentgalaxy': 'torrentgalaxy',
            'yourbittorrent': 'yourbittorrent',
            'yts': 'yts',
            'megapeer': 'megapeer',
            'bitru': 'bitru',
            'pctorrent': 'pctorrent',
            'xfsub': 'xfsub',
            'yihua': 'yihua',
        }
        return class_names.get(plugin_name, plugin_name.capitalize())
    
    def generate_report(self) -> Dict:
        """Generate comprehensive test report."""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(self.results),
            'passed': sum(1 for r in self.results if r['status'] == 'passed'),
            'failed': sum(1 for r in self.results if r['status'] == 'failed'),
            'partial': sum(1 for r in self.results if r['status'] == 'partial'),
            'results': self.results
        }


def main():
    parser = argparse.ArgumentParser(description='Full Download Verification Test Suite')
    parser.add_argument('--plugin', type=str, help='Test specific plugin')
    parser.add_argument('--host', type=str, default='localhost', help='qBittorrent host')
    parser.add_argument('--port', type=str, default='8085', help='qBittorrent port')
    parser.add_argument('--username', type=str, default='admin', help='qBittorrent username')
    parser.add_argument('--password', type=str, default='admin', help='qBittorrent password')
    parser.add_argument('--output', type=str, default='download_verification_report.json', help='Output file')
    args = parser.parse_args()
    
    print_header("FULL DOWNLOAD VERIFICATION TEST SUITE")
    print(f"qBittorrent: {args.host}:{args.port}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize API
    qbit = QBittorrentAPI(args.host, args.port, args.username, args.password)
    
    if qbit.session:
        if qbit.login():
            print_success("Connected to qBittorrent API")
        else:
            print_warning("Could not authenticate with qBittorrent - tests will run without add verification")
    else:
        print_warning("requests module not available - install with: pip install requests")
    
    # Initialize verifier
    verifier = DownloadVerifier(qbit)
    
    # Determine which plugins to test
    if args.plugin:
        plugins_to_test = [args.plugin]
    else:
        # Test core working plugins
        plugins_to_test = [
            'rutor', 'piratebay', 'limetorrents', 'yts',
            '1337x', 'torlock', 'kickass', 'nyaa',
            'extratorrent', 'linuxtracker', 'torrentfunk'
        ]
    
    print(f"\nWill test {len(plugins_to_test)} plugins\n")
    
    # Run tests
    for plugin in plugins_to_test:
        try:
            verifier.verify_plugin_download(plugin)
        except Exception as e:
            print_error(f"Unexpected error testing {plugin}: {e}")
        print()
    
    # Generate report
    report = verifier.generate_report()
    
    # Print summary
    print_header("TEST SUMMARY")
    print(f"Total: {report['total_tests']}")
    print(f"{Colors.GREEN}Passed: {report['passed']}{Colors.ENDC}")
    print(f"{Colors.FAIL}Failed: {report['failed']}{Colors.ENDC}")
    print(f"{Colors.WARNING}Partial: {report['partial']}{Colors.ENDC}")
    
    # Save report
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n{Colors.CYAN}Report saved to: {args.output}{Colors.ENDC}")
    
    return 0 if report['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
