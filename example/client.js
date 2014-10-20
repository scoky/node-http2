#!/user/bin/env node

var fs = require('fs')
var path = require('path')
var http2 = require('..')

// Logging
http2.globalAgent = new http2.Agent({
  log: require('../test/util').createLogger('client')
})
// Ignore cert errors
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"

// Parse argv
var argv = require('minimist')(process.argv.slice(2))
if (argv.h || argv._.length != 1) {
  console.log('USAGE: node client.js <url> [-p proxy:port] [-v] [-h] [-t times] [-o file]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-t number of times to perform the request')
  console.log('-v print status code and headers of response')
  console.log('-o write output to file')
  console.log('-h print this help menu')
  process.exit()
}

var options = require('url').parse(argv._[0])
// Always use HTTPS
options.protocol = 'https:'
options.plain = false
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
if (!argv.t) {
  argv.t = 1
}

// Sending the request
// It would be `var request = http2.get(process.argv.pop());` if we wouldn't care about plain mode
// console.log('Sending '+JSON.stringify(options, null, '\t'))
function run() {
  var request = http2.request(options)
  request.end()

  // Receiving the response
  request.on('response', function(response) {
    if (argv.v) {
      console.log('CODE='+response.statusCode)
      console.log('HEADERS='+JSON.stringify(response.headers, null, '\t')+'\n')
    }
    if (argv.o) {
      response.pipe(fs.createWriteStream(argv.o))
    } else {
      response.pipe(process.stdout)
    }

    response.on('end', finish)
  })

  // Receiving push streams - IGNORE PUSH FOR NOW
  /*request.on('push', function(pushRequest) {
    var filename = path.join(__dirname, '/push-' + push_count)
    push_count += 1
    console.error('Receiving pushed resource: ' + pushRequest.url + ' -> ' + filename)
    pushRequest.on('response', function(pushResponse) {
      pushResponse.pipe(fs.createWriteStream(filename)).on('finish', finish)
    })
  })*/
}

var time = process.hrtime()
// Perform the first request
//for (var i = 0; i < argv.t; i++) {
run()
//}

// Quitting after both the response and the associated pushed resources have arrived
var finished = 0
function finish() {
  finished += 1
  if (finished >= argv.t) {
    console.log('')
    if (argv.v) {
      time = process.hrtime(time)
      console.log('LOAD_TIME='+(time[0] + time[1]/1000000000).toFixed(3)+'s')
    }
    process.exit()
  } else {
    setTimeout(run, 1000)
  }
}
