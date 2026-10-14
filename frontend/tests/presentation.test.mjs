import test from "node:test";
import assert from "node:assert/strict";
import { datasetAssessmentLabel, datasetAssessmentTone, displayOriginalValue, isPotentialIssue, readColumnAssessment } from "../src/presentation.ts";

test("an assessment with remaining findings does not claim to be clean", () => {
  const item = { status: "COMPLETED", assessment_status: "PASSED", finding_count: 2 };
  assert.equal(datasetAssessmentLabel(item), "Perlu pemeriksaan");
  assert.equal(datasetAssessmentTone(item), "warning");
});

test("completed assessment with no findings uses a bounded claim", () => {
  const item = { status: "COMPLETED", assessment_status: "PASSED", finding_count: 0 };
  assert.equal(datasetAssessmentLabel(item), "Tanpa temuan");
  assert.equal(datasetAssessmentTone(item), "success");
});

test("processing and failure take precedence over stored assessment status", () => {
  assert.equal(datasetAssessmentLabel({ status: "FAILED", assessment_status: "PASSED", finding_count: 0 }), "Gagal");
  assert.equal(datasetAssessmentTone({ status: "PROCESSING", assessment_status: "PASSED", finding_count: 0 }), "neutral");
});

test("source values distinguish null, empty, whitespace, N/A and zero", () => {
  assert.deepEqual([null, "", "  ", "N/A", 0, "0"].map(displayOriginalValue), ["NULL", '""', "␠␠", "N/A", "0", "0"]);
});

test("statistical and semantic suspicions are not presented as certain errors", () => {
  assert.equal(isPotentialIssue("STATISTICAL_ANOMALY"), true);
  assert.equal(isPotentialIssue("POTENTIAL_TYPO"), true);
  assert.equal(isPotentialIssue("MISSING_VALUE"), false);
});

test("zero findings do not imply full assessment when a column is ambiguous", () => {
  const item = { status: "COMPLETED", assessment_status: "PASSED", finding_count: 0, pending_column_count: 1 };
  assert.equal(datasetAssessmentLabel(item), "Belum diperiksa penuh");
  assert.equal(datasetAssessmentTone(item), "warning");
});

test("missing or malformed coverage does not imply fully checked columns", () => {
  assert.equal(readColumnAssessment({}), null);
  assert.equal(readColumnAssessment({ column_assessment: { columns: [{ column: "nilai", status: "ready" }] } }), null);
  const column = { column: "nilai", status: "needs_role", suggested_role: "numeric", effective_role: "unclassified", source: "automatic", reason: "Ambigu" };
  assert.deepEqual(readColumnAssessment({ column_assessment: { columns: [column] } }), [column]);
});
