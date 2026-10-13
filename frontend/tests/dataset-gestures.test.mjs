import assert from "node:assert/strict";
import test from "node:test";
import { datasetSwipeOutcome } from "../src/datasetGestures.ts";

test("short gestures do not expose deletion", () => {
  assert.equal(datasetSwipeOutcome(0), "closed");
  assert.equal(datasetSwipeOutcome(39), "closed");
});
test("first swipe reveals the delete button without confirming", () => {
  assert.equal(datasetSwipeOutcome(40), "reveal");
  assert.equal(datasetSwipeOutcome(88), "reveal");
  assert.equal(datasetSwipeOutcome(169), "reveal");
});
test("long swipe asks for confirmation, cancellation never does", () => {
  assert.equal(datasetSwipeOutcome(170), "confirm");
  assert.equal(datasetSwipeOutcome(220), "confirm");
  assert.equal(datasetSwipeOutcome(220, true), "closed");
});
