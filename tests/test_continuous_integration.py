#!/usr/bin/env python3
"""
Continuous Integration Test Suite

This test suite is designed to run continuously or on a schedule
to monitor plugin health over time.

Features:
- Runs all plugin tests automatically
- Tracks success/failure rates over time
- Generates trend reports
- Alerts on failures
- Can be run via cron job or CI/CD pipeline

Usage:
    python3 tests/test_continuous_integration.py
    python3 tests/test_continuous_integration.py --schedule hourly
    python3 tests/test_continuous_integration.py --notify
"""

import os
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PLUGINS_DIR = os.path.join(PROJECT_DIR, "plugins")
sys.path.insert(0, PLUGINS_DIR)
sys.path.insert(0, SCRIPT_DIR)


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


class ContinuousIntegrationTester:
    """Runs continuous integration tests for all plugins."""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(SCRIPT_DIR, '.ci_data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.history_file = os.path.join(self.data_dir, 'test_history.json')
        
    def run_all_tests(self) -> Dict:
        """Run comprehensive tests on all plugins."""
        print_header("CONTINUOUS INTEGRATION TEST SUITE")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {}
        }
        
        # Run master test suite
        print_info("Running master test suite...")
        try:
            result = subprocess.run(
                ['python3', os.path.join(SCRIPT_DIR, 'test_master_all_plugins.py'), '--quick'],
                capture_output=True,
                text=True,
                timeout=300
            )
            results['tests']['master_suite'] = {
                'status': 'passed' if result.returncode == 0 else 'failed',
                'returncode': result.returncode,
                'output': result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
            }
        except Exception as e:
            results['tests']['master_suite'] = {'status': 'error', 'error': str(e)}
        
        # Run extended tests
        print_info("Running extended tests...")
        try:
            result = subprocess.run(
                ['python3', os.path.join(SCRIPT_DIR, 'test_all_plugins_extended.py')],
                capture_output=True,
                text=True,
                timeout=300
            )
            results['tests']['extended'] = {
                'status': 'passed' if result.returncode == 0 else 'failed',
                'returncode': result.returncode
            }
        except Exception as e:
            results['tests']['extended'] = {'status': 'error', 'error': str(e)}
        
        # Run download verification
        print_info("Running download verification...")
        try:
            result = subprocess.run(
                ['python3', os.path.join(SCRIPT_DIR, 'test_download_verification.py')],
                capture_output=True,
                text=True,
                timeout=300
            )
            results['tests']['download'] = {
                'status': 'passed' if result.returncode == 0 else 'failed',
                'returncode': result.returncode
            }
        except Exception as e:
            results['tests']['download'] = {'status': 'error', 'error': str(e)}
        
        # Load history and update
        history = self._load_history()
        history.append(results)
        
        # Keep only last 100 runs
        if len(history) > 100:
            history = history[-100:]
        
        self._save_history(history)
        
        # Generate summary
        summary = self._generate_summary(history)
        results['summary'] = summary
        
        return results
    
    def _load_history(self) -> List[Dict]:
        """Load test history."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self, history: List[Dict]):
        """Save test history."""
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def _generate_summary(self, history: List[Dict]) -> Dict:
        """Generate summary statistics from history."""
        if not history:
            return {'status': 'no_data'}
        
        # Calculate trends
        total_runs = len(history)
        passed_runs = sum(1 for h in history if all(
            t.get('status') in ['passed', 'success'] 
            for t in h.get('tests', {}).values()
        ))
        
        # Get last 24 hours
        day_ago = datetime.now() - timedelta(hours=24)
        recent_runs = [h for h in history if 
                       datetime.fromisoformat(h['timestamp']) > day_ago]
        
        return {
            'total_runs': total_runs,
            'passed_runs': passed_runs,
            'success_rate': (passed_runs / total_runs * 100) if total_runs > 0 else 0,
            'recent_runs_24h': len(recent_runs),
            'last_run': history[-1]['timestamp'] if history else None,
            'status': 'healthy' if passed_runs == total_runs else 'degraded'
        }
    
    def generate_trend_report(self) -> str:
        """Generate HTML trend report."""
        history = self._load_history()
        
        if not history:
            return "<h1>No test history available</h1>"
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>qBittorrent Plugin CI Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #333; color: white; padding: 20px; }
        .summary { background: #f0f0f0; padding: 15px; margin: 20px 0; }
        .passed { color: green; }
        .failed { color: red; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #4CAF50; color: white; }
        tr:nth-child(even) { background: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>qBittorrent Plugin CI Report</h1>
        <p>Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Runs: """ + str(len(history)) + """</p>
        <p>Success Rate: """ + f"{sum(1 for h in history if all(t.get('status') in ['passed', 'success'] for t in h.get('tests', {}).values())) / len(history) * 100:.1f}" + """%</p>
    </div>
    
    <h2>Recent Test Runs</h2>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>Master Suite</th>
            <th>Extended</th>
            <th>Download</th>
        </tr>
"""
        
        for run in reversed(history[-20:]):
            timestamp = datetime.fromisoformat(run['timestamp']).strftime('%Y-%m-%d %H:%M')
            tests = run.get('tests', {})
            
            master_status = tests.get('master_suite', {}).get('status', 'unknown')
            extended_status = tests.get('extended', {}).get('status', 'unknown')
            download_status = tests.get('download', {}).get('status', 'unknown')
            
            html += f"""
        <tr>
            <td>{timestamp}</td>
            <td class="{master_status}">{master_status}</td>
            <td class="{extended_status}">{extended_status}</td>
            <td class="{download_status}">{download_status}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        return html
    
    def check_health(self) -> bool:
        """Check if all systems are healthy."""
        history = self._load_history()
        
        if not history:
            return True
        
        last_run = history[-1]
        tests = last_run.get('tests', {})
        
        # Check if all recent tests passed
        for test_name, test_result in tests.items():
            if test_result.get('status') not in ['passed', 'success']:
                print_error(f"Test '{test_name}' failed in last run")
                return False
        
        return True
    
    def schedule_run(self, interval: str = 'hourly'):
        """Schedule periodic test runs."""
        print_header(f"SCHEDULING {interval.upper()} TEST RUNS")
        print_info(f"Starting continuous testing (press Ctrl+C to stop)")
        
        intervals = {
            'hourly': 3600,
            'daily': 86400,
            'weekly': 604800
        }
        
        seconds = intervals.get(interval, 3600)
        
        try:
            while True:
                self.run_all_tests()
                print_info(f"Waiting {seconds} seconds until next run...")
                time.sleep(seconds)
        except KeyboardInterrupt:
            print_info("Stopped by user")


def main():
    parser = argparse.ArgumentParser(description='Continuous Integration Test Suite')
    parser.add_argument('--run', action='store_true', help='Run tests once')
    parser.add_argument('--schedule', type=str, choices=['hourly', 'daily', 'weekly'], 
                       help='Run tests on schedule')
    parser.add_argument('--report', action='store_true', help='Generate HTML report')
    parser.add_argument('--check-health', action='store_true', help='Check if healthy')
    parser.add_argument('--output', type=str, default='ci_report.html', help='Report output file')
    args = parser.parse_args()
    
    tester = ContinuousIntegrationTester()
    
    if args.schedule:
        tester.schedule_run(args.schedule)
    elif args.run:
        results = tester.run_all_tests()
        print(json.dumps(results['summary'], indent=2))
        return 0 if results['summary'].get('status') == 'healthy' else 1
    elif args.report:
        html = tester.generate_trend_report()
        with open(args.output, 'w') as f:
            f.write(html)
        print(f"Report saved to: {args.output}")
    elif args.check_health:
        healthy = tester.check_health()
        print("Healthy" if healthy else "Unhealthy")
        return 0 if healthy else 1
    else:
        parser.print_help()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
