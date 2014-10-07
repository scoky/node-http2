var CS = require('coffee-script')
CS.register()
var Browser = require("../../zombie/src/zombie")

var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length < 1) {
  console.log('USAGE: node client.js <url> [timeout] [-p proxy:port] [-v] [-h]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-h print this help menu')
  process.exit()
}

tout = argv._[1] || '-1'
tout = parseInt(tout)

browser = Browser.create()
// Proxy present
if (argv.p) {
  browser.setProxy(argv.p)
}
// Do not use dns or ports map. Do not work.
//Browser.dns.map('*', 'A', '195.235.93.225')
//Browser.ports.map('195.235.93.225', 3456)
if (tout != -1) {
  setTimeout(function() { process.exit(1) }, tout*1000)
}

browser.visit(argv._[0], function () {
  browser.assert.success()
  process.exit(0)
});

