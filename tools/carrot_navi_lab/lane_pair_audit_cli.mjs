import { createReadStream } from "node:fs";
import { createInterface } from "node:readline";
import { audit, regression } from "./lane_pair_audit.mjs";
if (process.argv[2] === "--self-test" && process.argv.length === 3) {
  const tests = regression(); console.log(JSON.stringify({passed:tests.length,tests},null,2));
} else {
  if (process.argv.length !== 3) { console.error("Usage: node lane_pair_audit_cli.mjs <lane-observe.jsonl> | --self-test"); process.exit(2); }
  const rows=[];
  for await (const line of createInterface({input:createReadStream(process.argv[2]),crlfDelay:Infinity})) {
    if (!line.trim()) continue;
    if (rows.length>=9000 || line.length>131072) throw Error("record limit exceeded");
    rows.push(JSON.parse(line));
  }
  console.log(JSON.stringify(audit(rows),null,2));
}
