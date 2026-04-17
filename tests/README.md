# Test Documentation

## Overview

This directory contains comprehensive test suites for the qBitTorrent setup project.

## Test Scripts

### test.sh (Simple Tests)

Located in the project root, provides quick validation:

```bash
./test.sh              # Quick validation
./test.sh --all        # All validation tests
./test.sh --plugin     # Plugin configuration tests
./test.sh --full       # Complete test suite
./test.sh --container  # Container status only
```

### run_tests.sh (Comprehensive Tests)

Located in `tests/` directory, provides detailed testing:

```bash
./tests/run_tests.sh              # Run all test suites
./tests/run_tests.sh --quick      # Quick validation only
./tests/run_tests.sh --list       # List available suites
./tests/run_tests.sh --suite NAME # Run specific suite
./tests/run_tests.sh --ci         # CI mode (no colors)
```

## Test Suites

The comprehensive test suite includes:

1. **structure** - Project structure validation
2. **syntax** - Syntax validation for all files
3. **runtime** - Container runtime detection
4. **credentials** - Credentials configuration and security
5. **plugin** - RuTracker plugin functionality
6. **install** - Plugin installation script tests
7. **scripts** - Start/stop scripts validation
8. **container** - Container operation tests
9. **docs** - Documentation completeness
10. **security** - Security and credential safety

## What Gets Tested

### Project Structure
- Required files and directories
- File permissions and executability
- .gitkeep files for directory tracking

### Syntax Validation
- YAML syntax for docker-compose.yml
- Python syntax for plugins
- Bash syntax for all scripts

### Container Runtime
- Podman or Docker availability
- Compose command availability
- docker-compose.yml validation

### Credentials
- No credentials in git repository
- .gitignore patterns for secrets
- Environment variable configuration
- .env and ~/.qbit.env files
- .env.example has placeholders only

### Plugin Functionality
- Plugin file exists and is valid
- Environment variable loading
- RUTRACKER_USER alias support
- Required class structure

### Container Operations
- Container running status
- Port availability
- Web UI accessibility
- Correct image usage
- Plugin installation in container

### Documentation
- README.md completeness
- USER_MANUAL.md exists
- AGENTS.md comprehensive
- .env.example variables

### Security
- No .env in git
- No credentials in committed files
- Comprehensive .gitignore
- No hardcoded credentials

## Running Tests

### Before Committing

Always run tests before committing:

```bash
# Quick check
./test.sh

# Full validation
./tests/run_tests.sh
```

### Continuous Integration

For CI/CD pipelines:

```bash
./tests/run_tests.sh --ci
```

## Test Results

Tests produce clear output with:
- ✓ PASS - Test passed
- ✗ FAIL - Test failed
- ○ SKIP - Test skipped (with reason)

Final summary shows:
- Total tests run
- Passed count
- Failed count
- Skipped count
- Duration

## Adding New Tests

To add new tests to the comprehensive suite:

1. Create a new test function in `run_tests.sh`
2. Follow the naming convention: `test_<category>()`
3. Use assertion functions: `assert_*`
4. Call `test_pass()` or `test_fail()` appropriately
5. Add to the appropriate suite or create new suite
6. Update suite selection in `main()` function

## Troubleshooting

### Test Failures

If tests fail:

1. Check the specific test output
2. Review the reason provided
3. Fix the underlying issue
4. Re-run tests to verify

### Common Issues

- **Container not running**: Start with `./start.sh`
- **Credentials not configured**: Set in .env or environment
- **Permission denied**: Check file permissions
- **Syntax errors**: Review and fix the file

## TDD Workflow (MANDATORY)

**For every bug fix and feature, follow this process:**

1. **RED** - Write failing test first
   - Write test that reproduces the bug or tests the new feature
   - Run test and verify it FAILS

2. **GREEN** - Write minimal code to pass
   - Implement the minimal code needed for test to pass
   - Run test and verify it PASSES

3. **REFACTOR** - Clean up if needed (after green)

**Never write production code before a failing test.** If you write code first, delete it and start with tests.

## Best Practices

1. Run tests before every commit
2. Fix all failures before merging
3. Keep tests updated with code changes
4. Add new tests for new features
5. Document test requirements in AGENTS.md
