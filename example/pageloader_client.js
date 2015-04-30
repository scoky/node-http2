#!/usr/bin/env node

var http2 = require('..');
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
});

var req_counter = 0
process.on('uncaughtException', function(err) {
  console.log('ERROR='+err);
  // Typically, this is a protocol error
  var req_count = req_counter
  setTimeout(function() {
    if (req_count == req_counter) {
      console.log(getTimeString()+' TIMEOUT')
      process.exit(0)
    }
  }, 5000)
});

var CS = require('coffee-script')
CS.register()
var Browser = require("../../zombie/src/zombie")

var protocols = ['h2', 'http/1.1', 'spdy']
var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length < 1) {
  console.log('USAGE: node pageloader_client.js <url> [-t timeout] [-p proxy:port] [-r <'+protocols.toString()+'>] [-v] [-u user-agent] [-l tcp_limit] [-c] [-h]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-r indicate a protocol to use, (default '+protocols[0]+')')
  console.log('-t timeout in seconds')
  console.log('-v verbose output')
  console.log('-u user-agent header')
  console.log('-l limit the number of tcp connections to a single domain')
  console.log('-c exclude content')
  console.log('-h print this help menu')
  process.exit()
}

var browser = Browser.create()
// Proxy present
if (argv.p) {
  browser.setProxy(argv.p)
}

if (argv.u) {
  browser.userAgent = argv.u
}
if(argv.l) {
  browser.tcpLimit = argv.l
}

if (!argv.r || protocols.indexOf(argv.r) === -1) {
  argv.r = protocols[0]
}
browser.setProtocol(argv.r)

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
  req_counter += 1
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
    if (!argv.c && res.headers['content-type'] && (res.headers['content-type'].indexOf('text') !== -1 ||
      res.headers['content-type'].indexOf('html') !== -1)) {
      console.log(getTimeString()+' CONTENT=...')
      console.log(res.body.toString())
      console.log('...=CONTENT')
    }
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
  pushReq.on('error', function(err) {
    console.log(err)
  })
  pushReq.cancel()
})

browser.on('newConnection', function(endpoint, hostname, port) {
  if (argv.v) {
    console.log(getTimeString()+' TCP_CONNECTION='+JSON.stringify(endpoint, null, '\t')+' ENDPOINT='+hostname+':'+port)
  }
})

browser.on('protocolNegotiated', function(protocol, hostname, port) {
  if (argv.v) {
    console.log(getTimeString()+' PROTOCOL='+protocol+' ENDPOINT='+hostname+':'+port)
  }
  if (!protocol || protocol.indexOf('h2') !== 0) {
    console.log(getTimeString()+' PROTOCOL_NEGOTIATE_FAILED ENDPOINT='+hostname+':'+port)
    var req_count = req_counter
    setTimeout(function() {
      if (req_count == req_counter) {
        console.log(getTimeString()+' TIMEOUT')
        process.exit(0)
      }
    }, 5000)
  }
})

browser.visit(argv._[0], function () {
// Success throws an error if all objects are not loaded. Since we want to load partial webpages with a single protocol, dont use this.
//  browser.assert.success()
// Poorly structured output. We can do better.
//  browser.resources.dump()

  // Despite what Zombie documentation would tell you, the page is not actually loaded at this point.
  // Set a timer and watch for end of activity
  function waitForDone() {
    var req_count = req_counter
    setTimeout(function() {
      if (req_count == req_counter) {
        console.log(getTimeString()+' DONE')
        process.exit(0)
      } else {
        waitForDone()
      }
    }, 5000)
  }
  waitForDone()
});

