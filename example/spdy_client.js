#!/usr/bin/env node

var fs = require('fs')
var path = require('path')
var spdy = require('spdy')
var http = require('http')
var https = require('https')

process.on('uncaughtException', function(err) {
  console.log(getTimeString()+' ERROR='+err);
  // Typically, this is a protocol error
});

// Parse argv
var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node client.js <url> [-p proxy:port] [-k] [-f] [-v] [-h] [-t timeout] [-n times] [-o file] [-u user-agent header] [-a accept header] [-e accept-encoding header]')
  console.log('-p indicate a spdy TLS proxy to use')
  console.log('-t timeout in seconds')
  console.log('-n number of times to perform the request')
  console.log('-v verbose output')
  console.log('-o write output to file')
  console.log('-f follow redirects')
  console.log('-k ignore certificate errors')
  console.log('-u user-agent header (default curl/7.38.0)')
  console.log('-a accept header (default */*)')
  console.log('-e accept-encoding header (default *)')
  console.log('-h print this help menu')
  process.exit()
}
if (!argv.n) {
  argv.n = 1
}
if (argv.k) {
  // Ignore cert errors
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"
}
if (argv.t > 0) {
  setTimeout(timedout, argv.t*1000)
}

function createOptions(url) {
  var options = require('url').parse(url)

  options.plain = options.protocol == 'http:'
  options.headers = {
    'host' : options.hostname,
    'user-agent' : argv.u || 'curl/7.38.0', // Let's make them think we are curl for now
    'accept' : argv.a || '*/*',
    'accept-encoding' : argv.e || '*'
  }
  options.servername = options.hostname
  options.agent = spdy.createAgent({
    host: options.hostname,
    port: (options.plain ? 80 : 443),
  });

  // Proxy present
  if (argv.p) {
    options.hostname = options.host = argv.p.split(':')[0]
    options.port = argv.p.split(':')[1]
  }
  return options
}


// Sending the request
// It would be `var request = http2.get(process.argv.pop());` if we wouldn't care about plain mode
// console.log('Sending '+JSON.stringify(options, null, '\t'))
function run(url) {
  var options = createOptions(url)
  var request = null

  if (argv.v) {
    console.log(getTimeString()+' REQUEST='+options.href)
  }
  if (options.plain) {
    request = http.request(options)
  } else {
    request = https.request(options)
  }
  if (argv.v) {
    request.on('newConnection', function(endpoint) {
      console.log(getTimeString()+' TCP_CONNECTION='+JSON.stringify(endpoint, null, '\t'))
    })
  }
  request.on('protocolNegotiated', function(protocol) {
    if (argv.v) {
      console.log(getTimeString()+' PROTOCOL='+protocol)
    }
    if (!protocol || protocol.indexOf('h2') !== 0) {
      console.log(getTimeString()+' PROTOCOL_NEGOTIATE_FAILED')
      process.exit(0)
    }
  })
  request.on('error', function(err) {
    console.log(getTimeString()+' ERROR='+err)
  })
  request.end()

  // Receiving the response
  request.on('response', function(response) {
    if (argv.v) {
      console.log(getTimeString()+' RESPONSE='+options.href)
      console.log(getTimeString()+' CODE='+response.statusCode)
      console.log(getTimeString()+' HEADERS='+JSON.stringify(response.headers, null, '\t')+'\n')
    }
    // Following redirect
    if (argv.f && (response.statusCode >= 300 && response.statusCode < 400) && response.headers['location']) {
      var nurl = require('url').resolve(options.href, response.headers['location'])
      if (argv.v) {
	console.log(getTimeString()+' REDIRECT='+nurl)
      }
      run(nurl)

      // Read the data and ignore
      response.on('data', function(data) {})
      response.on('end', function() {})
    } else {
      if (argv.o) {
        response.pipe(fs.createWriteStream(argv.o))
      } else {
        console.log(getTimeString()+' CONTENT=...')
        response.pipe(process.stdout)
      }
      response.on('end', finish)
    }
  })

  // Receiving push streams
  request.on('push', function(pushRequest) {
    if (argv.v) {
      console.log(getTimeString()+' PUSH='+pushRequest.url)
    }
    pushRequest.on('error', function(err) {
      console.log(err)
    })
    pushRequest.cancel()
  })
}

var time = process.hrtime()
// Run the load for the first time
run(argv._[0])

function getTimeString() {
  var tval = process.hrtime(time)
  return '['+(tval[0] + tval[1]/1000000000).toFixed(3)+'s]'
}

var finished = 0
// Finished loading the object
function finish() {
  finished += 1
  // Run the load the requested number of times
  if (finished >= argv.n) {
    console.log('')
    if (argv.v) {
      console.log(getTimeString()+' DONE')
    }
    setImmediate(process.exit)
  } else {
    // Run it all again
    setTimeout(run, 100, argv._[0])
  }
}

function timedout() {
  console.log(getTimeString()+' TIMEOUT')
  process.exit(0)
}
