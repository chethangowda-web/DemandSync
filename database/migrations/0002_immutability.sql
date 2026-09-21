-- Locked demand and the audit trail must never be silently changed.
CREATE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% is immutable: % not allowed', TG_TABLE_NAME, TG_OP USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER demand_locks_immutable BEFORE UPDATE OR DELETE ON demand_locks
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER dataset_imports_no_delete BEFORE DELETE ON dataset_imports
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- A manifest past VALIDATED is sealed: its content fields cannot change and it cannot be deleted.
-- Only the lifecycle status (and dispatch bookkeeping) may advance.
CREATE FUNCTION protect_locked_manifest() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.manifest_status NOT IN ('DRAFT','VALIDATED') THEN
      RAISE EXCEPTION 'locked manifest % cannot be deleted', OLD.manifest_id USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.manifest_status NOT IN ('DRAFT','VALIDATED') AND (
       NEW.total_kg IS DISTINCT FROM OLD.total_kg
    OR NEW.sha256_hash IS DISTINCT FROM OLD.sha256_hash
    OR NEW.qr_payload IS DISTINCT FROM OLD.qr_payload
    OR NEW.vehicle_id IS DISTINCT FROM OLD.vehicle_id
    OR NEW.warehouse_id IS DISTINCT FROM OLD.warehouse_id
    OR NEW.cycle IS DISTINCT FROM OLD.cycle) THEN
    RAISE EXCEPTION 'locked manifest % is sealed', OLD.manifest_id USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER manifest_sealed BEFORE UPDATE OR DELETE ON dispatch_manifests
  FOR EACH ROW EXECUTE FUNCTION protect_locked_manifest();
