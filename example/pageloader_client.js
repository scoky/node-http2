#!/usr/bin/env node

var http2 = require('..');
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
});

var CS = require('coffee-script')
CS.register()
var Browser = require("../../zombie/src/zombie")

var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length < 1) {
  console.log('USAGE: node pageloader_client.js <url> [-t timeout] [-p proxy:port] [-v] [-h]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-t timeout in seconds')
  console.log('-v verbose output')
  console.log('-h print this help menu')
  process.exit()
}

var browser = Browser.create()
// Proxy present
if (argv.p) {
  browser.setProxy(argv.p)
}
// Do not use dns or ports map. Do not work.
//Browser.dns.map('*', 'A', '195.235.93.225')
//Browser.ports.map('195.235.93.225', 3456)
if (argv.t) {
  browser.waitDuration = argv.t*1000-500
  // Give the browser a brief chance to clean up (hence -500)
  setTimeout(function() { 
    console.log(getTimeString()+' TIMEOUT')
    process.exit(0) 
  }, argv.t*1000)
}
// Start the timer
var time = process.hrtime()
function getTimeString() {
  var tval = process.hrtime(time)
  return '['+(tval[0] + tval[1]/1000000000).toFixed(3)+'s]'
}

var reqs = []
var reps = []
browser.on('request', function(req) {
  // Prevent duplicates
  if (reqs.indexOf(req.url) !== -1) {
    return
  }
  reqs.push(req.url)

  if (argv.v) {
    console.log(getTimeString()+' REQUEST='+req.url)
  }
})

browser.on('response', function(req, res) {
  // Prevent duplicates
  if (reps.indexOf(res.url) !== -1) {
    return
  }
  reps.push(res.url)

  if (argv.v) {
    console.log(getTimeString()+' RESPONSE='+res.url+' SIZE='+Buffer(res.body).length)
    console.log(getTimeString()+' CODE='+res.statusCode)
    console.log(getTimeString()+' HEADERS='+JSON.stringify(res.headers, null, '\t')+'\n')
  }
})

browser.on('redirect', function(req, res, red) {
  // Prevent duplicates
  if (reps.indexOf(req.url) !== -1) {
    return
  }
  reps.push(req.url)

  if (argv.v) {
    console.log(getTimeString()+' RESPONSE='+req.url+' SIZE='+Buffer(res.body).length)
    console.log(getTimeString()+' CODE='+res.statusCode)
    console.log(getTimeString()+' HEADERS='+JSON.stringify(res.headers, null, '\t')+'\n')
    console.log(getTimeString()+' REDIRECT='+red.url)
  }
})

browser.on('push', function(pushReq) {
  if (argv.v) {
    console.log(getTimeString()+' PUSH='+pushReq.url)
  }
  pushReq.cancel()
})

browser.on('newConnection', function(endpoint) {
  if (argv.v) {
    console.log(getTimeString()+' TCP_CONNECTION='+JSON.stringify(endpoint, null, '\t'))
  }
})

browser.on('protocolNegotiated', function(protocol) {
  if (argv.v) {
    console.log(getTimeString()+' PROTOCOL='+protocol)
  }
  if (protocol === undefined || protocol.indexOf('h2') !== 0) {
    console.log(getTimeString()+' PROTOCOL_NEGOTIATE_FAILED')
    process.exit(2)
  }
})

browser.visit(argv._[0], function () {
  browser.assert.success()
//  Poorly structure output. We can do better
//  browser.resources.dump()

  console.log(getTimeString()+' DONE')
  process.exit(0)
});

