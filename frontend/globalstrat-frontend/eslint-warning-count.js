#!/usr/bin/env node
/**
 * Count the ESLint warnings a production build reports, and refuse an increase.
 *
 * `CI=true react-scripts build` turns every warning into an error. This project
 * carries 57 of them — 46 unused variables and 11 exhaustive-deps — spread over
 * 18 page components, none of which GSP-CRV2-05 touches. Making the build fail
 * on them would either block the toolchain work behind an unrelated cleanup, or
 * push someone into editing hook dependency arrays in a competition engine to
 * get a build out, which is how render loops arrive.
 *
 * So warnings do not fail the build, and instead the count cannot grow: new
 * code is held to zero without anyone having to clean up first. Lower the
 * baseline whenever warnings are fixed; raising it should be a conversation.
 *
 * Usage: node eslint-warning-count.js <build log>
 */
const fs = require('fs');

const logPath = process.argv[2];
const baselinePath = `${__dirname}/.eslint-warning-baseline`;

const log = fs.readFileSync(logPath, 'utf8');
const baseline = parseInt(fs.readFileSync(baselinePath, 'utf8').trim(), 10);

// Every reported warning is a line of the form "  Line 12:34:  message  rule".
const count = (log.match(/^\s+Line \d+:\d+:/gm) || []).length;

if (/Failed to compile/.test(log)) {
  console.error('The build failed to compile; warnings are not the issue.');
  process.exit(1);
}

console.log(`eslint warnings: ${count} (baseline ${baseline})`);
if (count > baseline) {
  console.error(
    `New lint warnings: ${count} > ${baseline}. Fix them, or state why the `
    + 'baseline should move.');
  process.exit(1);
}
if (count < baseline) {
  console.log(`Warnings are down; lower ${baselinePath} to ${count}.`);
}
process.exit(0);
