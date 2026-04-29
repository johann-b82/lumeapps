import { describe, it, expect } from "vitest";
import {
  buildSensorUpdatePayload,
  validateSensorDraft,
  SensorDraftValidationError,
  type SensorDraftRow,
  type SensorDraftGlobals,
} from "./useSensorDraft";

function baseRow(overrides: Partial<SensorDraftRow> = {}): SensorDraftRow {
  return {
    _localId: "srv-1",
    id: 1,
    name: "Hall A",
    host: "192.9.201.27",
    port: 161,
    community: "",
    communityDirty: false,
    temperature_oid: ".1.3.6.1.4.1.1.1",
    humidity_oid: ".1.3.6.1.4.1.1.2",
    temperature_scale: "1.0",
    humidity_scale: "1.0",
    enabled: true,
    hasStoredCommunity: true,
    _markedForDelete: false,
    ...overrides,
  };
}

function baseGlobals(
  overrides: Partial<SensorDraftGlobals> = {},
): SensorDraftGlobals {
  return {
    sensor_poll_interval_s: 60,
    sensor_temperature_min: "",
    sensor_temperature_max: "",
    sensor_humidity_min: "",
    sensor_humidity_max: "",
    ...overrides,
  };
}

describe("buildSensorUpdatePayload — community preservation", () => {
  it("OMITS community when communityDirty === false (preserves stored ciphertext)", () => {
    const snap = baseRow();
    const draft = baseRow({ name: "Hall B" }); // edited name, community untouched
    const body = buildSensorUpdatePayload(draft, snap);
    expect("community" in body).toBe(false);
    expect(body.name).toBe("Hall B");
  });

  it("includes community only when communityDirty AND non-empty", () => {
    const snap = baseRow();
    const draft = baseRow({ communityDirty: true, community: "new-secret" });
    const body = buildSensorUpdatePayload(draft, snap);
    expect(body.community).toBe("new-secret");
  });

  it("omits community when communityDirty but value is empty string", () => {
    // Edge case: user focused the input and then cleared it. Omit rather
    // than sending "" (backend SecretStr min_length=1 would 422).
    const snap = baseRow();
    const draft = baseRow({ communityDirty: true, community: "" });
    const body = buildSensorUpdatePayload(draft, snap);
    expect("community" in body).toBe(false);
  });

  it("empty OID string is sent as null (distinguish from 'no change')", () => {
    const snap = baseRow();
    const draft = baseRow({ temperature_oid: "" });
    const body = buildSensorUpdatePayload(draft, snap);
    expect(body.temperature_oid).toBe(null);
  });

  it("returns an empty body when nothing changed", () => {
    const snap = baseRow();
    const draft = baseRow();
    const body = buildSensorUpdatePayload(draft, snap);
    expect(Object.keys(body)).toHaveLength(0);
  });
});

describe("validateSensorDraft", () => {
  it("throws name_required on blank name", () => {
    expect(() =>
      validateSensorDraft([baseRow({ name: "" })], baseGlobals()),
    ).toThrowError(SensorDraftValidationError);
  });

  it("throws host_required on blank host", () => {
    expect(() =>
      validateSensorDraft([baseRow({ host: "" })], baseGlobals()),
    ).toThrowError(/host_required/);
  });

  it("throws name_duplicate when two live rows share a name", () => {
    const a = baseRow({ _localId: "a", id: 1, name: "dup" });
    const b = baseRow({ _localId: "b", id: 2, name: "dup" });
    expect(() => validateSensorDraft([a, b], baseGlobals())).toThrowError(
      /name_duplicate/,
    );
  });

  it("ignores marked-for-delete rows in the duplicate check", () => {
    const a = baseRow({ _localId: "a", id: 1, name: "dup", _markedForDelete: true });
    const b = baseRow({ _localId: "b", id: 2, name: "dup" });
    expect(() => validateSensorDraft([a, b], baseGlobals())).not.toThrow();
  });

  it("throws positive_number when scale <= 0", () => {
    expect(() =>
      validateSensorDraft([baseRow({ temperature_scale: "0" })], baseGlobals()),
    ).toThrowError(/positive_number/);
  });

  it("throws community_required when a NEW (id===null) row has blank community", () => {
    const newRow = baseRow({ id: null, _localId: "new", community: "" });
    expect(() => validateSensorDraft([newRow], baseGlobals())).toThrowError(
      /community_required/,
    );
  });

  it("throws poll_interval out-of-bounds at 4 and 86401", () => {
    expect(() =>
      validateSensorDraft(
        [baseRow()],
        baseGlobals({ sensor_poll_interval_s: 4 }),
      ),
    ).toThrowError(/out_of_bounds/);
    expect(() =>
      validateSensorDraft(
        [baseRow()],
        baseGlobals({ sensor_poll_interval_s: 86401 }),
      ),
    ).toThrowError(/out_of_bounds/);
  });

  it("accepts a valid new row with community", () => {
    const newRow = baseRow({
      id: null,
      _localId: "new",
      community: "public-override",
    });
    expect(() => validateSensorDraft([newRow], baseGlobals())).not.toThrow();
  });
});
