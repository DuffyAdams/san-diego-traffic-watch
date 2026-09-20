import test from "node:test";
import assert from "node:assert/strict";
import { classifyActivity } from "../traffic-app/src/utils/activityStatus.js";

const classify = (current, average, overrides = {}) => classifyActivity({
  current, average, sampleCount: 6, hasData: true, ...overrides,
});

test("missing data and insufficient history never report elevated activity", () => {
  assert.equal(classify(20, 0, { hasData: false }), "noData");
  for (const sampleCount of [undefined, null, 0, 1, 2, NaN]) {
    assert.equal(classify(20, 0, { sampleCount }), "insufficientHistory");
  }
  for (const average of [null, undefined, NaN, -1, Infinity]) {
    assert.equal(classify(20, average), "insufficientHistory");
  }
});

test("quiet baselines require a meaningful absolute increase", () => {
  assert.equal(classify(0, 0), "nominal");
  assert.equal(classify(1, 0), "nominal");
  assert.equal(classify(2, 0.1), "nominal");
  assert.equal(classify(3, 0), "elevatedIncidents");
  assert.equal(classify(5, 0), "highActivity");
});

test("activity bands compare volume with history, independent of chart peaks", () => {
  assert.equal(classify(10, 10), "nominal");
  assert.equal(classify(12, 10), "nominal");
  assert.equal(classify(15, 10), "elevatedIncidents");
  assert.equal(classify(20, 10), "highActivity");
  assert.equal(classify(7, 10), "lightIncidents");
  assert.equal(classify(0, 10), "lightIncidents");
  assert.equal(classify(0, 2), "nominal");
});
