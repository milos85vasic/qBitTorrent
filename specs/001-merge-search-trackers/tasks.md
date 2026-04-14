---

description: "Task list template for feature implementation"
---

# Tasks: Merge Search Results Across Trackers

**Input**: Design documents from `/specs/001-merge-search-trackers/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create directory structure for merge service per plan.md in download-proxy/src/
- [x] T002 Initialize Python package files (__init__.py) in all new directories
- [x] T003 [P] Configure pytest and pytest-asyncio in tests/requirements.txt
- [x] T004 [P] Create initial conftest.py with qBittorrent test fixtures
- [x] T005 Add python-Levenshtein, aiohttp to download-proxy dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create SearchResult entity model in download-proxy/src/merge_service/search.py
- [x] T007 Create MergedResult entity model in download-proxy/src/merge_service/search.py
- [x] T008 Create TrackerSource entity model in download-proxy/src/merge_service/search.py
- [x] T009 Create CanonicalIdentity entity model in download-proxy/src/merge_service/search.py
- [x] T010 Create data-model.yaml in config/merge-service/ for runtime config
- [x] T011 [P] Set up FastAPI app router in download-proxy/src/api/__init__.py
- [x] T012 [P] Create environment variable loader for OMDb/TMDB keys
- [x] T013 Add API routes to download-proxy service startup (verify T011 dependency)
- [x] T014 Run python -m py_compile on all new Python files (verify syntax)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Unified Search Results with Merged Trackers (Priority: P1) 🎯 MVP

**Goal**: Search across all trackers and merge duplicate results into single entries

**Independent Test**: Search for Ubuntu, verify results from 3+ trackers merge into single entry

### Tests for User Story 1 (OPTIONAL)

> **NOTE: Tests are included for validation - write these first, ensure they FAIL before implementation**

- [x] T015 [P] [US1] Write contract test for POST /search endpoint in tests/contract/test_search_api.py
- [x] T016 [P] [US1] Write integration test for merged results deduplication in tests/integration/test_dedup.py

### Implementation for User Story 1

- [x] T017 [US1] Implement tiered matching engine in download-proxy/src/merge_service/deduplicator.py
- [x] T018 [US1] Implement search orchestration in download-proxy/src/merge_service/search.py (depends on T006, T007, T008, T009, T013)
- [x] T019 [US1] Create SSE streaming response handler in download-proxy/src/api/streaming.py
- [x] T020 [US1] Implement POST /search endpoint in download-proxy/src/api/routes.py (depends on T018, T019)
- [x] T021 [US1] Implement GET /search/stream/{searchId} streaming endpoint in download-proxy/src/api/routes.py (depends on T019)
- [x] T022 [US1] Add multi-tracker download URL wiring in download-proxy/src/api/routes.py (depends on T020)
- [x] T023 [US1] Create search result aggregation logic in download-proxy/src/merge_service/search.py (depends on T017, T018)
- [x] T024 [US1] Verify python -m py_compile on all modified files
- [x] T025 [US1] Run integration tests for search endpoint (depends on T015, T016, T017, T018, T020, T021)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Tracker Validation and Dead Tracker Elimination (Priority: P2)

**Goal**: Validate each tracker source before including in merged results

**Independent Test**: Add a dead tracker to search, verify it's excluded from results

### Tests for User Story 2 (OPTIONAL)

- [x] T026 [P] [US2] Write contract test for tracker scrape validation in tests/contract/test_validator.py

### Implementation for User Story 2

- [x] T027 [US2] Implement HTTP scrape client in download-proxy/src/merge_service/validator.py
- [x] T028 [US2] Implement tracker health status checking in download-proxy/src/merge_service/validator.py (depends on T027)
- [x] T029 [US2] Integrate validator into search orchestration in download-proxy/src/merge_service/search.py (depends on T028, T018)
- [x] T030 [US2] Handle offline tracker fallback logic in download-proxy/src/merge_service/search.py (depends on T029)
- [x] T031 [US2] Verify python -m py_compile on validator.py
- [x] T032 [US2] Run integration tests (depends on T026, T027, T028, T029, T030)
- [x] T032b [US2] Implement UDP scrape fallback in download-proxy/src/merge_service/validator.py
- [x] T032c [US2] Add UDP timeout handling (5-second timeout, graceful fallback to HTTP-only) (depends on T032b)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Metadata Enrichment for Better Matching (Priority: P3)

**Goal**: Use external APIs to accurately identify content across trackers

**Independent Test**: Search for a movie with different names on multiple trackers, verify metadata resolution

### Tests for User Story 3 (OPTIONAL)

- [x] T033 [P] [US3] Write contract test for metadata API enrichment in tests/contract/test_enricher.py

### Implementation for User Story 3

- [x] T034 [US3] Implement OMDb API client in download-proxy/src/merge_service/enricher.py
- [x] T035 [US3] Implement TMDB API client in download-proxy/src/merge_service/enricher.py
- [x] T036 [US3] Implement TVMaze API client in download-proxy/src/merge_service/enricher.py
- [x] T037 [US3] Implement AniList API client in download-proxy/src/merge_service/enricher.py
- [x] T038 [US3] Implement MusicBrainz API client in download-proxy/src/merge_service/enricher.py
- [x] T039 [US3] Implement OpenLibrary API client in download-proxy/src/merge_service/enricher.py
- [x] T040 [US3] Create metadata resolver facade in download-proxy/src/merge_service/enricher.py (depends on T034, T035, T036, T037, T038, T039)
- [x] T041 [US3] Integrate enricher into search flow in download-proxy/src/merge_service/search.py (depends on T040, T018)
- [x] T042 [US3] Add quality detection parsing in download-proxy/src/merge_service/enricher.py
- [x] T043 [US3] Verify python -m py_compile (depends on T034-T042)
- [x] T044 [US3] Run integration tests (depends on T033, T034-T042)

**Checkpoint**: At this point, all User Stories should work independently

---

## Phase 6: User Story 4 - Pipeline Event Hooks System (Priority: P4)

**Goal**: Fire events at pipeline stages for custom script execution

**Independent Test**: Configure a hook, trigger a search/download, verify event fires with data

### Tests for User Story 4 (OPTIONAL)

- [x] T045 [P] [US4] Write contract test for hook execution in tests/contract/test_hooks.py

### Implementation for User Story 4

- [x] T046 [US4] Define HookEvent model in download-proxy/src/merge_service/hooks.py
- [x] T047 [US4] Define HookConfig model in download-proxy/src/merge_service/hooks.py
- [x] T048 [US4] Implement hook event dispatcher in download-proxy/src/merge_service/hooks.py (depends on T046, T047)
- [x] T049 [US4] Implement bash script executor with timeout in download-proxy/src/merge_service/hooks.py (depends on T048)
- [x] T050 [US4] Create default logging hook script in config/merge-service/log_event.sh
- [x] T051 [US4] Implement GET/POST /hooks API endpoints in download-proxy/src/api/hooks.py
- [x] T052 [US4] Add hook firing to search orchestration in download-proxy/src/merge_service/search.py (depends on T048, T049, T050)
- [x] T053 [US4] Add hook firing to download flow in download-proxy/src/api/routes.py (depends on T052)
- [x] T054 [US4] Create hooks.yaml configuration file in config/merge-service/
- [x] T055 [US4] Verify python -m py_compile (depends on T046-T053)
- [x] T056 [US4] Run integration tests (depends on T045, T046-T053)

**Checkpoint**: At this point, User Story 4 should be fully functional

---

## Phase 7: User Story 5 - Comprehensive Test Suite with Real Downloads (Priority: P5)

**Goal**: Full end-to-end tests with real downloads verifying the entire pipeline

**Independent Test**: Run full test suite against live qBittorrent, verify Ubuntu download completes

### Tests for User Story 5

- [x] T057 [US5] Write end-to-end test for full search-merge-download pipeline in tests/e2e/test_full_pipeline.py
- [x] T058 [US5] Write unit tests for deduplicator in tests/unit/merge_service/test_deduplicator.py
- [x] T059 [US5] Write unit tests for metadata enricher in tests/unit/merge_service/test_enricher.py
- [x] T060 [US5] Write unit tests for tracker validator in tests/unit/merge_service/test_validator.py
- [x] T061 [US5] Write unit tests for hooks system in tests/unit/merge_service/test_hooks.py
- [x] T062 [US5] Run full test suite with coverage report

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T063 [P] Add real-time download monitoring GET /downloads/active endpoint in download-proxy/src/api/routes.py (add SSE streaming for real-time progress)
- [x] T063b [P] Implement SSE endpoint for download progress updates in download-proxy/src/api/streaming.py
- [x] T064 [P] Implement automated scheduling (cron) in download-proxy/src/merge_service/scheduler.py (add persistence - save/restore scheduled searches across restarts)
- [x] T064b [P] Implement scheduler persistence (save/restore scheduled searches across restarts)
- [x] T065 [P] Create scheduling API endpoints in download-proxy/src/api/routes.py
- [x] T066 [P] Build web UI dashboard in download-proxy/src/ui/templates/dashboard.html
- [x] T067 [P] Add health check GET /health endpoint in download-proxy/src/api/__init__.py
- [x] T068 Update README.md and PLUGIN_STATUS.md with merge service documentation
- [x] T069 Run full validation: python -m py_compile on all files
- [x] T070 Run bash -n on all hook scripts
- [x] T071 Run test.sh --quick to verify setup integrity
- [x] T072 Run run-all-tests.sh for full validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational - Depends on US1 infrastructure (deduplicator)
- **User Story 3 (P3)**: Can start after Foundational - No dependencies on other stories  
- **User Story 4 (P4)**: Can start after Foundational - Depends on US1 search flow existing
- **User Story 5 (P5)**: Can start after Foundational - Requires US1-US4 complete

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for POST /search endpoint in tests/contract/test_search_api.py"
Task: "Integration test for merged results deduplication in tests/integration/test_dedup.py"

# Launch implementation in parallel:
Task: "Implement tiered matching engine in download-proxy/src/merge_service/deduplicator.py"
Task: "Create SSE streaming response handler in download-proxy/src/api/streaming.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Story 5 → Test independently → Deploy/Demo
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2  
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence