.PHONY: schema-fixture-update ci-guards test-sse test-authz test-allowlists help

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
help:
	@echo "KPI Dashboard Makefile — Phase 65 CI targets"
	@echo ""
	@echo "  schema-fixture-update  Regenerate directus/fixtures/schema-hash.txt"
	@echo "                         Run after intentional DDL changes (alembic upgrade head first)"
	@echo ""
	@echo "  ci-guards              Run all 4 CI guards locally (requires docker compose up -d)"
	@echo "    Guard A: DDL hash matches fixture"
	@echo "    Guard B: Directus snapshot diff"
	@echo "    Guard C: DB_EXCLUDE_TABLES superset"
	@echo "    Guard D: --workers 1 invariant"
	@echo ""
	@echo "  test-sse               Run SSE-04 integration tests (requires docker compose up -d)"
	@echo "  test-authz             Run AUTHZ-05 Viewer permission tests (requires docker compose up -d)"
	@echo "  test-allowlists        Run Pydantic-vs-shell allowlist parity tests (pure-python, no stack)"
	@echo ""

# ---------------------------------------------------------------------------
# Guard A — regenerate schema hash fixture.
# Run AFTER: docker compose up -d && docker compose run --rm migrate alembic upgrade head
#
# This computes md5() of (table_name, column_name, data_type, is_nullable,
# column_default) for all v1.22-surfaced tables and writes the result to
# directus/fixtures/schema-hash.txt. Commit the updated fixture after running.
# ---------------------------------------------------------------------------
schema-fixture-update:
	@echo "Regenerating schema hash fixture..."
	@docker compose up -d db
	@docker compose run --rm migrate alembic upgrade head
	@set -a; [ -f .env ] && . ./.env; set +a; \
	docker compose exec -T db psql \
	  -U "$${POSTGRES_USER:-kpi}" \
	  -d "$${POSTGRES_DB:-kpi}" \
	  -tA -c "\
	    SELECT md5(string_agg(row_data, '|' ORDER BY row_data)) \
	    FROM ( \
	      SELECT concat_ws(',', \
	        table_name, column_name, data_type, is_nullable, \
	        coalesce(column_default, '') \
	      ) AS row_data \
	      FROM information_schema.columns \
	      WHERE table_schema = 'public' \
	        AND table_name IN ( \
	          'signage_devices','signage_playlists','signage_playlist_items', \
	          'signage_device_tags','signage_playlist_tag_map', \
	          'signage_device_tag_map','signage_schedules', \
	          'sales_records','personio_employees' \
	        ) \
	    ) s;" \
	  2>/dev/null | tr -d '[:space:]' > directus/fixtures/schema-hash.txt
	@echo "Fixture updated: $$(cat directus/fixtures/schema-hash.txt)"
	@echo "Remember to: git add directus/fixtures/schema-hash.txt && git commit"

# ---------------------------------------------------------------------------
# CI guards — run all 4 guards against the live stack
# ---------------------------------------------------------------------------
ci-guards:
	@bash scripts/ci/check_schema_hash.sh
	@bash scripts/ci/check_directus_snapshot_diff.sh
	@bash scripts/ci/check_db_exclude_tables_superset.sh
	@bash scripts/ci/check_workers_one_invariant.sh

# ---------------------------------------------------------------------------
# Test targets
# ---------------------------------------------------------------------------

# SSE-04 integration tests — requires live docker compose stack
test-sse:
	@cd backend && pytest tests/signage/test_pg_listen_sse.py -v

# AUTHZ-05 Viewer permission integration tests — requires live stack
test-authz:
	@cd backend && pytest tests/signage/test_viewer_authz.py -v

# Pydantic-vs-shell allowlist parity tests — pure-python, no docker stack needed
test-allowlists:
	@cd backend && pytest tests/signage/test_permission_field_allowlists.py -v
