const fs = require("node:fs");
const vm = require("node:vm");

const lines = fs.readFileSync(0, "utf8").trim().split("\n");
for (const line of lines) {
  const item = JSON.parse(line);
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(item.source, "utf8"), context);
  context.input = {
    bytes: Array.from(Buffer.from(item.payload, "hex")),
    fPort: item.f_port,
  };
  try {
    // Round-trip through JSON so results from the sandbox are plain data.
    const result = vm.runInContext("JSON.stringify(decodeUplink(input))", context, {
      timeout: 1000,
    });
    item.expected = result === undefined ? null : JSON.parse(result);
  } catch (error) {
    item.error = error.toString();
  }
  delete item.source;
  process.stdout.write(JSON.stringify(item) + "\n");
}
