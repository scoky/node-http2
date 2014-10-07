var CS = require('coffee-script')
CS.register()
var Browser = require("/home/b.kyle/github/zombie/src/zombie")

var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node client.js <url> [-p proxy:port] [-v] [-h]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-h print this help menu')
  process.exit()
}

browser = Browser.create()
// Proxy present
if (argv.p) {
  browser.setProxy(argv.p)
}
// Do not use dns or ports map. Do not work.
//Browser.dns.map('*', 'A', '195.235.93.225')
//Browser.ports.map('195.235.93.225', 3456)

browser.visit(argv._[0], function () {
  browser.assert.success()
  setTimeout(function() { process.exit() }, 5000)
});

