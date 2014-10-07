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
  console.log('USAGE: node client.js <url> [-p proxy:port] [-v] [-h]')
  console.log('-p indicate a HTTP2 TLS proxy to use')
  console.log('-v print status code and headers of response')
  console.log('-h print this help menu')
  process.exit()
}

var options = require('url').parse(argv._[0])
// Always use HTTPS
options.protocol = 'https:'
options.plain = false
options.headers = {
  ':authority' : options.hostname
}
// Proxy present
if (argv.p) {
  options.hostname = options.host = argv.p.split(':')[0]
  options.port = argv.p.split(':')[1]
}
options = {"protocol":"https:","slashes":true,"auth":null,"host":"mplane.pdi.tid.es","port":4567,"hostname":"mplane.pdi.tid.es","hash":null,"search":null,"query":null,"pathname":"/","path":"/","href":"https://nghttp2.org:4567/","headers":{"user-agent":"Mozilla/5.0 Chrome/10.0.613.0 Safari/534.15 Zombie.js/2.0.4","referer":"","accept":"text/html",":authority":"nghttp2.org"},"plain":false}

// Sending the request
// It would be `var request = http2.get(process.argv.pop());` if we wouldn't care about plain mode
// console.log('Sending '+JSON.stringify(options, null, '\t'))
var request = http2.request(options)
request.end()

// Receiving the response
request.on('response', function(response) {
  if (argv.v) {
    console.log('CODE='+response.statusCode)
    console.log('HEADERS='+JSON.stringify(response.headers, null, '\t')+'\n')
  }
  response.pipe(process.stdout)

  response.on('end', finish)
});

// Receiving push streams - IGNORE PUSH FOR NOW
/*request.on('push', function(pushRequest) {
  var filename = path.join(__dirname, '/push-' + push_count);
  push_count += 1;
  console.error('Receiving pushed resource: ' + pushRequest.url + ' -> ' + filename);
  pushRequest.on('response', function(pushResponse) {
    pushResponse.pipe(fs.createWriteStream(filename)).on('finish', finish);
  });
});*/

// Quitting after both the response and the associated pushed resources have arrived
var push_count = 0
var finished = 0
function finish() {
  finished += 1
  if (finished === (1 + push_count)) {
    process.exit()
  }
}
