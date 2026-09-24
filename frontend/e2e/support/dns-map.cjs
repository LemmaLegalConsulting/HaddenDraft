// Resolve *.cle.test to loopback for Playwright's Node-side request context,
// which does not see Chromium's --host-resolver-rules.
const dns = require("dns");
const original = dns.lookup;
dns.lookup = function lookup(hostname, options, callback) {
  if (typeof hostname === "string" && hostname.endsWith(".cle.test")) {
    if (typeof options === "function") { callback = options; options = {}; }
    if (options && options.all) return process.nextTick(callback, null, [{ address: "127.0.0.1", family: 4 }]);
    return process.nextTick(callback, null, "127.0.0.1", 4);
  }
  return original.apply(this, arguments);
};
const originalPromise = dns.promises.lookup;
dns.promises.lookup = async function lookup(hostname, options = {}) {
  if (typeof hostname === "string" && hostname.endsWith(".cle.test")) {
    const family = typeof options === "object" ? options.family : options;
    if (family === 6) return options.all ? [] : Promise.reject(Object.assign(new Error("no v6"), { code: "ENOTFOUND" }));
    return options.all ? [{ address: "127.0.0.1", family: 4 }] : { address: "127.0.0.1", family: 4 };
  }
  return originalPromise.apply(this, arguments);
};
