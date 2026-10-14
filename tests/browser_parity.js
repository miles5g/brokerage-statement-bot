/* Write browser-pipeline files for a Python byte comparison. */
"use strict";

const fs = require("fs");
const path = require("path");
const pipeline = require("../docs/pipeline.js");

const activityPath = process.argv[2];
const ledgerPath = process.argv[3];
const ytdPath = process.argv[4];
const outDir = process.argv[5];

if (!activityPath || !ledgerPath || !ytdPath || !outDir) {
  console.error("usage: node tests/browser_parity.js activity.csv ledger.csv ytd.csv outdir");
  process.exit(2);
}

const activity = pipeline.parseCsv(fs.readFileSync(activityPath, "utf8"));
const ledger = pipeline.parseCsv(fs.readFileSync(ledgerPath, "utf8"));
const ytd = pipeline.parseCsv(fs.readFileSync(ytdPath, "utf8"));
const result = pipeline.buildOutputFiles(activity, ledger, ytd);
fs.mkdirSync(outDir, { recursive: true });
for (const name of pipeline.OUTPUT_NAMES) {
  fs.writeFileSync(path.join(outDir, name), result.files[name]);
}
