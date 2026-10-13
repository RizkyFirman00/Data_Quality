export function datasetSwipeOutcome(distance: number, cancelled = false): "closed" | "reveal" | "confirm" {
  if (cancelled || distance < 40) return "closed";
  return distance >= 170 ? "confirm" : "reveal";
}
