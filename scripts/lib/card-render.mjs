// Shared paths and built-in theme for study-cards PNG output.
import path from "node:path";
import { WORKSPACE } from "./cli.mjs";

/** Single built-in style from skills/study-cards (dark palette). */
export const CARD_THEME = "dark";

export const STUDY_CARDS_DIR = path.join(WORKSPACE, "skills", "study-cards");
export const RENDER_ORCHESTRATOR = path.join(
  WORKSPACE,
  "skills",
  "study-plan-cards",
  "scripts",
  "render.js"
);
export const RENDER_TABLE_JS = path.join(STUDY_CARDS_DIR, "render-table.js");
