-- Phase 1: beneficiary service journey.

-- Human-readable references for records created through the app (dataset rows keep their own ids).
CREATE SEQUENCE intent_reference_seq START 1;
CREATE SEQUENCE grievance_reference_seq START 100001;

-- A grievance can be tied to a cycle and to the e-PoS transaction it is about.
ALTER TABLE grievances
  ADD COLUMN cycle TEXT REFERENCES cycles(cycle),
  ADD COLUMN related_transaction_id TEXT REFERENCES epos_transactions(transaction_id);

CREATE INDEX idx_grievances_beneficiary ON grievances(beneficiary_id, created_at DESC);
CREATE INDEX idx_intent_beneficiary ON intent_signals(beneficiary_id, cycle);
CREATE INDEX idx_epos_beneficiary_time ON epos_transactions(beneficiary_id, transaction_time DESC);
