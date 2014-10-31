#!/user/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')

// Logging
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})

// Parse argv
var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node client.js <url> [-p proxy:port] [-k] [-f] [-v] [-h] [-t times] [-o file]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-t number of times to perform the request')
  console.log('-v verbose output')
  console.log('-o write output to file')
  console.log('-f follow redirects')
  console.log('-k ignore certificate errors')
  console.log('-h print this help menu')
  process.exit()
}
if (!argv.t) {
  argv.t = 1
}
if (argv.k) {
  // Ignore cert errors
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"
}

function createOptions(url) {
  var options = require('url').parse(url)

  options.plain = options.protocol == 'http:'
  options.headers = {
    ':authority' : options.hostname,
    'user-agent' : 'curl/7.38.0', // Let's make them think we are curl for now
    'accept' : '*/*'
  }
  options.servername = options.hostname

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
  if (options.plain) {
    request = http2.raw.request(options)
  } else {
    request = http2.request(options)
  }
  if (argv.v) {
    request.on('newConnection', function(endpoint) {
      console.log(toStringTime(process.hrtime(time))+' TCP_CONNECTION='+JSON.stringify(endpoint, null, '\t'))
    })
    request.on('protocolNegotiated', function(protocol) {
      console.log(toStringTime(process.hrtime(time))+' PROTOCOL='+protocol)
    })
  }
  request.on('error', function(err) {
    console.log('ERROR='+err)
  })
  request.end()

  // Receiving the response
  request.on('response', function(response) {
    if (argv.v) {
      console.log(toStringTime(process.hrtime(time))+' RESPONSE='+options.href)
      console.log(toStringTime(process.hrtime(time))+' CODE='+response.statusCode)
      console.log(toStringTime(process.hrtime(time))+' HEADERS='+JSON.stringify(response.headers, null, '\t')+'\n')
    }
    // Following redirect
    if (argv.f && (response.statusCode >= 300 && response.statusCode < 400) && response.headers['location']) {
      var nurl = require('url').resolve(options.href, response.headers['location'])
      if (argv.v) {
	console.log(toStringTime(process.hrtime(time))+' REDIRECT='+nurl)
      }
      run(nurl)

      // Read the data and ignore
      response.on('data', function(data) {})
      response.on('end', function() {})
    } else {
      if (argv.o) {
        response.pipe(fs.createWriteStream(argv.o))
      } else {
        response.pipe(process.stdout)
      }
      response.on('end', finish)
    }
  })

  // Receiving push streams
  request.on('push', function(pushRequest) {
    if (argv.v) {
      console.log(toStringTime(process.hrtime(time))+' PUSH='+pushRequest.url)
    }
    pushRequest.cancel()
  })
}

var time = process.hrtime()
// Run the load for the first time
run(argv._[0])

function toStringTime(tval) {
  return '['+(tval[0] + tval[1]/1000000000).toFixed(3)+'s]'
}

var finished = 0
// Finished loading the object
function finish() {
  finished += 1
  // Run the load the requested number of times
  if (finished >= argv.t) {
    console.log('')
    if (argv.v) {
      console.log(toStringTime(process.hrtime(time))+' DONE')
    }
    process.exit()
  } else {
    // Run it all again
    setTimeout(run, 100, argv._[0])
  }
}
