-- Phase 2 Slice 2: same lesson as migration 0006 (demand_forecast). The seeded dataset already ships one
-- allocations row per (cycle, fps_id, commodity) for every historical/current cycle, including 2026-03.
-- Add the constraint so the allocation engine updates that existing row (INSERT ... ON CONFLICT) instead
-- of being blocked by it, or silently duplicating it.
ALTER TABLE allocations ADD CONSTRAINT uq_allocations_cycle_fps_commodity UNIQUE (cycle, fps_id, commodity);
