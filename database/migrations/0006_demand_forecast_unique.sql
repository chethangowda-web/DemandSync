-- Phase 2 Slice 1: demand_forecast is keyed by (fps_id, cycle, commodity) in practice — the seeded dataset
-- already has exactly one row per triple. Add the constraint so a re-run of the forecast pipeline updates
-- the existing row (INSERT ... ON CONFLICT) instead of silently creating a second one alongside it.
ALTER TABLE demand_forecast ADD CONSTRAINT uq_demand_forecast_fps_cycle_commodity UNIQUE (fps_id, cycle, commodity);
